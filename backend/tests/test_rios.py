"""
Tarea 'rios' (backend/ingesta/rios.py): avisos hidrológicos de SENAMHI con la web y la BD
simuladas. Sin red ni psycopg: solo librería estándar.

Usa las muestras reales de test_avisos_hidro.py (lista del 03-10-2026 y los detalles 67552 del
Mashcón y 70483 del Napo) y listas chicas armadas aquí para los casos raros.
"""
import gzip
import json
import logging
import unittest
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from backend.connectors import _http
from backend.connectors import senamhi_avisos_hidro as sh
from backend.connectors.senamhi import HORA_PERU
from backend.connectors.senamhi_avisos import ATRIBUCION
from backend.ingesta import rios as tarea
from backend.ingesta.guardar import SQL_LATIDO

MUESTRAS = Path(__file__).parent / "muestras"


def _leer(nombre: str) -> bytes:
    return gzip.decompress((MUESTRAS / nombre).read_bytes())


LISTA = _leer("avisos_hidrologicos_lista_20261003.html.gz")
MASHCON_ROJO = _leer("aviso_hidrologico_67552_mashcon_rojo.html.gz")
NAPO_DESCENSO = _leer("aviso_hidrologico_70483_napo_descenso.html.gz")

AHORA = datetime(2026, 10, 3, 6, 30, tzinfo=timezone.utc)      # 01:30 del 03-10 en Lima
HOY = date(2026, 10, 3)
MASHCON, NAPO = "220213", "240111"
VIGENTES_MUESTRA = [70483, 70487, 70481, 70482, 70485, 70486, 70488]


def _url(ca, ce):
    return sh.DETALLE_URL.format(ca=ca, ce=ce)


def _fila(ca, ce=MASHCON, numero=None, vigente=False, ini="2026-10-02", fin="2026-10-03", nivel="dos", clase=None):
    """Una fila como las de SENAMHI: los vigentes llevan "(vigente)" y class="vigente" en sus celdas."""
    enlace = f'<a href="./?p=avisos-detalle-hidrologicos&ca={ca}&ce={ce}">'
    nro = f"{numero or ca}{' (vigente)' if vigente else ''}"
    nivel = f'<span class="{nivel}">AMARILLO</span>' if nivel else ""
    celdas = [f"{enlace}INCREMENTO DEL CAUDAL DEL RÍO MASHCÓN - ESTACIÓN MASHCÓN</a>", f"{enlace}{nro}</a>",
              ini, fin, "24", nivel]
    atributo = ' class="vigente"' if (vigente if clase is None else clase) else ""
    return "<tr>" + "".join(f"<td{atributo}>{c}</td>" for c in celdas) + "</tr>"


def _lista(*filas, relleno=None) -> bytes:
    """Lista con `relleno` avisos viejos de otra estación (por defecto, los justos para pasar MIN_FILAS)."""
    relleno = tarea.MIN_FILAS + 10 if relleno is None else relleno
    viejos = [_fila(900000 + i, ce="999999", ini="2026-01-01", fin="2026-01-02") for i in range(relleno)]
    return ("<table><tbody>" + "".join(viejos + list(filas)) + "</tbody></table>").encode("utf-8")


def _detalle(numero: int, nivel: str = "ROJO") -> bytes:
    """
    El detalle real del Mashcón (aviso 1169), como si fuera del aviso `numero` y terminara el
    03-10-2026 a las 16:00 (el fin que da _fila por defecto).
    """
    return (MASHCON_ROJO.replace("Aviso N&deg;1169".encode(), f"Aviso N&deg;{numero}".encode())
            .replace('<span class="cuatro">ROJO</span></h2>'.encode(),
                     f'<span class="cuatro">{nivel}</span></h2>'.encode())
            .replace("Fecha de final: </strong>Viernes, 13 de Marzo de 2026".encode(),
                     "Fecha de final: </strong>Sábado, 3 de Octubre de 2026".encode()))


class _Web:
    """La web de SENAMHI simulada: {url: bytes o excepción}; anota los pedidos en orden."""

    def __init__(self, paginas):
        self.paginas, self.pedidos = paginas, []

    def get_bytes(self, url, max_bytes=None):
        self.pedidos.append(url)
        r = self.paginas[url]
        if isinstance(r, Exception):
            raise r
        return r


class _Cursor:
    def __init__(self, conn):
        self.conn, self.ultima, self.rowcount = conn, None, -1

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        c = self.conn
        c.registro.append((sql, params))
        self.ultima = sql
        if sql == tarea.SQL_NO_VIGENTES:
            for ca, a in c.avisos.items():
                if a["vigente"] and ca not in params[0]:
                    a["vigente"] = False
        elif sql == tarea.SQL_PURGA:
            viejos = [ca for ca, a in c.avisos.items() if a["fin_dia"] < params[0]]
            for ca in viejos:
                del c.avisos[ca]
            self.rowcount = len(viejos)

    def executemany(self, sql, filas):
        filas = list(filas)
        self.conn.registro.append((sql, filas))
        if sql == tarea.SQL_AVISO:          # upsert: solo las columnas de la lista; nivel = coalesce(nuevo, viejo)
            for p in filas:
                a = self.conn.avisos.setdefault(p["ca"], {"inicio": None, "nivel": None})
                a.update({k: v for k, v in p.items() if not (k == "nivel" and v is None)})
        elif sql == tarea.SQL_DETALLE:      # nivel = coalesce(el de la lista, el del detalle)
            for p in filas:
                a = self.conn.avisos[p["ca"]]
                nivel = a["nivel"] if a.get("nivel") is not None else p["nivel"]
                a.update(p)
                a["nivel"] = nivel

    def fetchone(self):
        assert self.ultima == tarea.SQL_HAY_TABLA, self.ultima
        return (self.conn.migrada,)

    def fetchall(self):
        if self.ultima == tarea.SQL_VIGILADAS:
            return [(ce,) for ce in self.conn.vigiladas]
        assert self.ultima == tarea.SQL_CON_DETALLE, self.ultima
        return [(ca, a["fin"].astimezone(HORA_PERU).date() if a.get("fin") else None, a.get("nivel"))
                for ca, a in self.conn.avisos.items() if a.get("inicio") is not None]


class _Conexion:
    """
    Anota cada sentencia y lleva aviso_hidrologico en memoria ({ca: columnas}). vigiladas: las
    estaciones de rio_vigilado. migrada: si están las tablas.
    """

    def __init__(self, vigiladas=(MASHCON,), avisos=None, migrada=True):
        self.vigiladas, self.migrada = list(vigiladas), migrada
        self.avisos = {ca: dict(a) for ca, a in (avisos or {}).items()}
        self.registro = []

    def cursor(self):
        return _Cursor(self)

    def params(self, sql):
        return [p for s, p in self.registro if s == sql]

    def sentencias(self):
        return [s for s, _ in self.registro]


class TestTarea(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.ERROR)   # la tarea avisa de las fallas simuladas
        self.addCleanup(logging.disable, logging.NOTSET)

    def correr(self, conn=None, lista=LISTA, detalles=None, ahora=AHORA):
        conn = conn or _Conexion()
        conn.registro.clear()                    # una segunda corrida sobre la misma BD
        paginas = {sh.LISTA_URL: lista, **(detalles or {})}
        self.web = _Web(paginas)
        self.pausas = 0

        @contextmanager
        def falso_conectar():
            yield conn

        def falsa_pausa():
            self.pausas += 1

        self.excepcion = None
        with mock.patch.object(tarea, "conectar", falso_conectar), \
             mock.patch.object(sh, "pausa", falsa_pausa), \
             mock.patch.object(_http, "get_bytes", self.web.get_bytes), \
             mock.patch.object(_http.time, "sleep", lambda s: None):
            try:
                devuelto = tarea.actualizar(ahora)
            except Exception as e:
                self.excepcion, devuelto = e, None
        [(servicio, datos)] = conn.params(SQL_LATIDO)   # el latido se escribe siempre
        self.assertEqual(servicio, "rios")
        resumen = json.loads(datos)
        if devuelto is not None:
            self.assertEqual(resumen, devuelto)
        return conn, resumen

    def test_corrida_con_la_muestra(self):
        conn, resumen = self.correr()
        self.assertIsNone(self.excepcion)
        # ningún aviso del Mashcón está vigente: solo se pide la lista
        self.assertEqual(self.web.pedidos, [sh.LISTA_URL])
        self.assertEqual(self.pausas, 0)
        s = conn.sentencias()
        self.assertEqual(s[:3], [tarea.SQL_HAY_TABLA, tarea.SQL_VIGILADAS, tarea.SQL_CON_DETALLE])
        self.assertEqual(s[3:], [tarea.SQL_CANDADO, tarea.SQL_AVISO, tarea.SQL_NO_VIGENTES, tarea.SQL_PURGA,
                                 SQL_LATIDO])   # el candado primero; sin detalles no hay SQL_DETALLE
        [filas] = conn.params(tarea.SQL_AVISO)
        self.assertEqual(len(filas), 1680)        # upsert de todas las filas
        f = next(p for p in filas if p["ca"] == 67739)
        self.assertEqual(f, {"ca": 67739, "ce": MASHCON, "numero": 1233,
                             "titulo": "INCREMENTO DEL CAUDAL DEL RÍO MASHCÓN - ESTACIÓN MASHCÓN", "nivel": 2,
                             "sentido": "crecida", "inicio_dia": date(2026, 3, 17), "fin_dia": date(2026, 3, 18),
                             "duracion_h": 24, "vigente": False, "url": _url(67739, MASHCON)})
        [(vigentes,)] = conn.params(tarea.SQL_NO_VIGENTES)
        self.assertEqual(sorted(vigentes), sorted(VIGENTES_MUESTRA))
        self.assertEqual(conn.params(tarea.SQL_PURGA), [(HOY - timedelta(days=400),)])
        self.assertEqual(resumen, {
            "filas": 1680, "vigentes": 7,
            "vigilados": [{"ce": MASHCON, "numero": 1233, "nivel": 2, "vigente": False, "fin_dia": "2026-03-18"}],
            "detalles": [], "purgados": 0, "fallas": [], "avisos": [], "atribucion": ATRIBUCION,
        })

    def test_detalle_de_un_vigilado_vigente(self):
        conn = _Conexion(vigiladas=[MASHCON, NAPO])
        conn, resumen = self.correr(conn, detalles={_url(70483, NAPO): NAPO_DESCENSO})
        self.assertIsNone(self.excepcion)
        self.assertEqual(self.web.pedidos, [sh.LISTA_URL, _url(70483, NAPO)])
        self.assertEqual(self.pausas, 1)         # en serie y con pausa
        [[d]] = conn.params(tarea.SQL_DETALLE)
        self.assertEqual((d["ca"], d["valor"], d["unidad"], d["umbral_rojo"]), (70483, 87.0, "m.s.n.m", 85.81))
        self.assertEqual(d["fin"].isoformat(), "2026-10-04T18:00:00-05:00")
        self.assertEqual(d["nivel"], 2)          # "Aviso N°1624 AMARILLO" (solo completa una lista sin nivel)
        self.assertNotIn("numero", d)            # no es una columna
        self.assertEqual(resumen["detalles"], [70483])
        self.assertEqual(resumen["vigilados"], [
            {"ce": MASHCON, "numero": 1233, "nivel": 2, "vigente": False, "fin_dia": "2026-03-18"},
            {"ce": NAPO, "numero": 1624, "nivel": 2, "vigente": True, "fin_dia": "2026-10-04"},
        ])
        # la siguiente corrida ya no lo pide
        _, resumen = self.correr(conn)
        self.assertEqual(self.web.pedidos, [sh.LISTA_URL])
        self.assertEqual(resumen["detalles"], [])
        self.assertEqual(conn.avisos[70483]["valor"], 87.0)   # el upsert de la lista no pisa el detalle

    def test_solo_vigilados_vigentes_sin_detalle_y_como_maximo_10(self):
        vigentes = [_fila(1000 + i, vigente=True, ini=f"2026-09-{10 + i:02d}") for i in range(13)]
        otros = [_fila(2000, ini="2026-08-01", fin="2026-08-02"), _fila(3000, ce=NAPO, vigente=True)]
        ya = {1012: {"vigente": True, "inicio": datetime(2026, 9, 22, 6, tzinfo=timezone.utc),
                     "fin_dia": date(2026, 10, 3)}}   # ya tiene detalle
        conn = _Conexion(avisos=ya)
        detalles = {_url(1000 + i, MASHCON): _detalle(1000 + i) for i in range(13)}
        conn, resumen = self.correr(conn, lista=_lista(*vigentes, *otros), detalles=detalles)
        self.assertIsNone(self.excepcion)
        # los más nuevos primero; el 1012 ya tenía detalle; 1000 y 1001 quedan para la próxima
        pedidos = list(range(1011, 1001, -1))
        self.assertEqual(self.web.pedidos, [sh.LISTA_URL] + [_url(ca, MASHCON) for ca in pedidos])
        self.assertEqual(self.pausas, 10)
        self.assertEqual(resumen["detalles"], pedidos)
        self.assertEqual([d["ca"] for d in conn.params(tarea.SQL_DETALLE)[0]], pedidos)
        self.assertEqual(resumen["avisos"], ["2 avisos vigilados sin detalle quedan para la próxima corrida "
                                             "(máximo 10 por corrida)"])
        self.assertEqual(resumen["fallas"], [])
        self.assertEqual(len(resumen["vigilados"]), 13)    # los 13 vigentes (el último ya es uno de ellos)

    def test_vigente_false_para_los_demas(self):
        previos = {
            # vigente en la BD, sale en la lista sin "(vigente)"
            5000: {"vigente": True, "inicio": None, "fin_dia": date(2026, 10, 3)},
            # vigente en la BD y ya no está en la lista
            4000: {"vigente": True, "inicio": None, "fin_dia": date(2025, 10, 1)},
            # terminó hace más de 400 días: se purga
            3000: {"vigente": False, "inicio": None, "fin_dia": date(2025, 8, 1)},
        }
        conn = _Conexion(avisos=previos)
        lista = _lista(_fila(5000), _fila(6000, vigente=True))
        conn, resumen = self.correr(conn, lista=lista, detalles={_url(6000, MASHCON): _detalle(6000)})
        self.assertIsNone(self.excepcion)
        self.assertEqual(conn.params(tarea.SQL_NO_VIGENTES), [([6000],)])
        self.assertFalse(conn.avisos[5000]["vigente"])
        self.assertFalse(conn.avisos[4000]["vigente"])
        self.assertTrue(conn.avisos[6000]["vigente"])
        self.assertNotIn(3000, conn.avisos)
        self.assertEqual(resumen["purgados"], 1)
        self.assertEqual(resumen["vigilados"], [{"ce": MASHCON, "numero": 6000, "nivel": 2, "vigente": True,
                                                 "fin_dia": "2026-10-03"}])

    def test_lista_rara_no_escribe(self):
        conn, resumen = self.correr(lista=_lista(_fila(1, vigente=True), relleno=tarea.MIN_FILAS - 10))
        self.assertIsInstance(self.excepcion, ValueError)
        self.assertEqual(conn.sentencias(), [tarea.SQL_HAY_TABLA, tarea.SQL_VIGILADAS, tarea.SQL_CON_DETALLE,
                                             SQL_LATIDO])
        self.assertEqual(self.web.pedidos, [sh.LISTA_URL])   # ni siquiera pide el detalle del vigente
        self.assertEqual(resumen["fallas"], ["lista_rara"])
        self.assertEqual(resumen["filas"], tarea.MIN_FILAS - 9)
        self.assertIn(f"la lista trae {tarea.MIN_FILAS - 9} avisos legibles", resumen["avisos"][0])
        # una página filtrada o recortada de 60 filas (antes pasaba con MIN_FILAS = 50), igual
        conn, resumen = self.correr(lista=_lista(_fila(1, vigente=True), relleno=60))
        self.assertEqual((resumen["fallas"], resumen["filas"]), (["lista_rara"], 61))
        self.assertNotIn(tarea.SQL_NO_VIGENTES, conn.sentencias())
        # una página sin tabla, igual
        conn, resumen = self.correr(lista=b"<html>Mantenimiento</html>")
        self.assertEqual((resumen["fallas"], resumen["filas"]), (["lista_rara"], 0))
        self.assertNotIn(tarea.SQL_AVISO, conn.sentencias())

    def test_lista_caida(self):
        conn, resumen = self.correr(lista=OSError("timed out"))
        self.assertIsInstance(self.excepcion, OSError)        # se relanza la del pedido
        self.assertEqual(len(self.web.pedidos), _http.INTENTOS)
        self.assertNotIn(tarea.SQL_CANDADO, conn.sentencias())
        self.assertEqual(resumen, {"filas": None, "vigentes": None, "vigilados": [], "detalles": [],
                                   "purgados": None, "fallas": ["lista"], "avisos": ["lista: OSError: timed out"],
                                   "atribucion": ATRIBUCION})

    def test_sin_migracion(self):
        conn, resumen = self.correr(_Conexion(migrada=False))
        self.assertIsNone(self.excepcion)
        self.assertEqual(conn.sentencias(), [tarea.SQL_HAY_TABLA, SQL_LATIDO])
        self.assertEqual(self.web.pedidos, [])
        self.assertEqual(resumen["fallas"], ["migracion"])
        self.assertEqual(resumen["avisos"], [tarea.AVISO_SIN_TABLA])

    def test_un_detalle_que_falla_no_frena_al_resto(self):
        lista = _lista(_fila(7003, vigente=True, ini="2026-10-03"), _fila(7002, vigente=True),
                       _fila(7001, vigente=True, ini="2026-10-01"), _fila(7000, vigente=True, ini="2026-09-30"))
        detalles = {_url(7003, MASHCON): OSError("timed out"),
                    _url(7002, MASHCON): _detalle(9999),                 # la página es de otro aviso
                    _url(7001, MASHCON): b"<html>sin aviso</html>",     # no se entiende
                    _url(7000, MASHCON): _detalle(7000)}
        conn, resumen = self.correr(lista=lista, detalles=detalles)
        self.assertIsNone(self.excepcion)
        self.assertEqual(resumen["fallas"], ["detalle:7003", "detalle:7002", "detalle:7001"])
        self.assertEqual(resumen["avisos"], [
            "detalle 7003 (aviso 7003): OSError: timed out",
            "detalle 7002: la página es del aviso 9999, no del 7002; no se guardó",
            "detalle 7001 (aviso 7001): no se entendió la página; no se guardó",
        ])
        self.assertEqual(resumen["detalles"], [7000])
        [[d]] = conn.params(tarea.SQL_DETALLE)
        self.assertEqual((d["ca"], d["valor"], d["umbral_rojo"]), (7000, 30.17, 18.0))
        self.assertTrue(d["significado_rojo"].startswith("Se espera desborde del río"))
        # la lista se escribió igual
        self.assertEqual(len(conn.params(tarea.SQL_AVISO)[0]), tarea.MIN_FILAS + 14)

    def test_detalle_incompleto_se_guarda_con_aviso(self):
        sin_inicio = _detalle(8000).replace(b"Fecha de inicio", b"Comienzo")
        conn, resumen = self.correr(lista=_lista(_fila(8000, vigente=True)),
                                    detalles={_url(8000, MASHCON): sin_inicio})
        self.assertEqual(resumen["fallas"], [])
        self.assertEqual(resumen["detalles"], [8000])
        self.assertEqual(resumen["avisos"], ["detalle 8000 (aviso 8000): no se encontró inicio "
                                             "(se vuelve a pedir en la próxima corrida)"])
        self.assertIsNone(conn.avisos[8000]["inicio"])
        self.assertEqual(conn.avisos[8000]["valor"], 30.17)

    def test_sin_tiempo_no_se_piden_detalles(self):
        with mock.patch.object(tarea, "PLAZO_S", -1):
            conn, resumen = self.correr(lista=_lista(_fila(8000, vigente=True)))
        self.assertIsNone(self.excepcion)
        self.assertEqual(self.web.pedidos, [sh.LISTA_URL])
        self.assertEqual(resumen["detalles"], [])
        self.assertIn("detalle 8000: no se pidió", resumen["avisos"][0])
        self.assertEqual(len(conn.params(tarea.SQL_AVISO)[0]), tarea.MIN_FILAS + 11)

    def test_sin_estaciones_vigiladas(self):
        conn, resumen = self.correr(_Conexion(vigiladas=[]))
        self.assertIsNone(self.excepcion)
        self.assertEqual(self.web.pedidos, [sh.LISTA_URL])
        self.assertEqual(resumen["vigilados"], [])
        self.assertEqual(resumen["avisos"], ["rio_vigilado no tiene estaciones SENAMHI: no se lee ningún detalle"])

    def test_vigencia_ambigua_no_apaga_ningun_aviso(self):
        # SENAMHI quita la marca de la fila (o el texto): el aviso se toma como vigente y no se apaga
        # ninguno de los que dejaron de figurar (4000); uno sin ninguna de las dos señales (5000) no es vigente
        previos = {5000: {"vigente": True, "inicio": None, "fin_dia": date(2026, 10, 3)},
                   4000: {"vigente": True, "inicio": None, "fin_dia": date(2026, 10, 3)}}
        for fila in (_fila(6000, vigente=True, clase=False),                    # "(vigente)" sin la marca
                     _fila(6000, vigente=False, clase=True)):                   # la marca sin "(vigente)"
            conn = _Conexion(avisos=previos)
            conn, resumen = self.correr(conn, lista=_lista(_fila(5000), fila),
                                        detalles={_url(6000, MASHCON): _detalle(6000)})
            self.assertIsNone(self.excepcion)
            self.assertEqual(resumen["fallas"], ["vigente_ambiguo"])
            self.assertIn("vigencia ambigua en 1 avisos (N.º 6000)", resumen["avisos"][0])
            self.assertNotIn(tarea.SQL_NO_VIGENTES, conn.sentencias())
            self.assertTrue(conn.avisos[4000]["vigente"])        # no se apagó
            self.assertFalse(conn.avisos[5000]["vigente"])       # la lista lo da sin ninguna señal
            self.assertTrue(conn.avisos[6000]["vigente"])
            self.assertEqual(resumen["detalles"], [6000])          # y se leyó su detalle
        # "(no vigente)" no es vigente
        [f] = [f for f in sh.parsear_lista(_lista(_fila(7000, numero="7000 (no vigente)")).decode()) if f.ca == 7000]
        self.assertEqual((f.vigente, f.ambiguo), (False, False))

    def test_detalle_viejo_se_vuelve_a_leer(self):
        # ya tienen detalle: 6000 terminaba el 03-10 y la lista ahora dice 05-10; 6001 pasó de amarillo a
        # naranja; 6002 no cambió
        fin_3 = datetime(2026, 10, 3, 16, tzinfo=HORA_PERU)
        ya = {ca: {"vigente": True, "inicio": datetime(2026, 10, 2, 6, tzinfo=HORA_PERU), "fin": fin_3, "nivel": 2,
                   "fin_dia": date(2026, 10, 3)} for ca in (6000, 6001, 6002)}
        conn = _Conexion(avisos=ya)
        lista = _lista(_fila(6000, vigente=True, fin="2026-10-05"), _fila(6001, vigente=True, nivel="tres"),
                       _fila(6002, vigente=True))
        extendido = _detalle(6000).replace("Sábado, 3 de Octubre de 2026 - 16:00".encode(),
                                           "Lunes, 5 de Octubre de 2026 - 18:00".encode())
        conn, resumen = self.correr(conn, lista=lista, detalles={_url(6000, MASHCON): extendido,
                                                                 _url(6001, MASHCON): _detalle(6001, "NARANJA")})
        self.assertIsNone(self.excepcion)
        self.assertEqual(self.web.pedidos, [sh.LISTA_URL, _url(6001, MASHCON), _url(6000, MASHCON)])
        self.assertEqual(sorted(resumen["detalles"]), [6000, 6001])
        self.assertEqual(conn.avisos[6000]["fin"], datetime(2026, 10, 5, 18, tzinfo=HORA_PERU))
        self.assertEqual(conn.avisos[6001]["nivel"], 3)
        self.assertEqual(conn.avisos[6002]["fin"], fin_3)
        self.assertIn("detalle 6000 (aviso 6000): se vuelve a leer (la lista cambió su fin o su nivel)",
                      resumen["avisos"])
        # la corrida siguiente ya no los pide
        self.correr(conn, lista=lista)
        self.assertEqual(self.web.pedidos, [sh.LISTA_URL])

    def test_nivel_del_detalle_completa_la_lista(self):
        # la lista no trae nivel (pasa con 66491 y 65908), el detalle dice "Aviso N°... ROJO"
        lista = _lista(_fila(8000, vigente=True, nivel=None))
        conn, resumen = self.correr(lista=lista, detalles={_url(8000, MASHCON): _detalle(8000)})
        self.assertIsNone(self.excepcion)
        self.assertEqual(conn.avisos[8000]["nivel"], 4)
        # la corrida siguiente (la lista sigue sin nivel) no lo borra
        self.correr(conn, lista=lista)
        self.assertEqual(conn.avisos[8000]["nivel"], 4)
        # si la lista trae nivel, manda la lista
        conn, _ = self.correr(lista=_lista(_fila(8001, vigente=True, nivel="tres")),
                              detalles={_url(8001, MASHCON): _detalle(8001)})
        self.assertEqual(conn.avisos[8001]["nivel"], 3)

    def test_detalle_que_no_cuadra_con_la_lista(self):
        # el fin del detalle es de otro día que el de la lista, y el caudal leído es 16 veces el umbral
        raro = (_detalle(8000).replace("Sábado, 3 de Octubre de 2026 - 16:00".encode(),
                                       "Domingo, 4 de Octubre de 2026 - 04:00".encode())
                .replace(b"30.17 m3/s", b"301.7 m3/s"))
        conn, resumen = self.correr(lista=_lista(_fila(8000, vigente=True)), detalles={_url(8000, MASHCON): raro})
        self.assertIsNone(self.excepcion)
        self.assertEqual(resumen["fallas"], [])
        self.assertEqual(resumen["avisos"], [
            "detalle 8000 (aviso 8000): su fin (04-10-2026 04:00) no es del día que da la lista (03-10-2026); "
            "no se guardó el fin",
            "detalle 8000 (aviso 8000): el valor 301.7 es más de 10 veces el umbral rojo 18 (¿lectura equivocada?); "
            "no se guardaron",
        ])
        a = conn.avisos[8000]
        self.assertEqual((a["fin"], a["valor"], a["umbral_rojo"]), (None, None, None))
        self.assertIsNotNone(a["inicio"])                 # lo demás sí se guarda
        self.assertTrue(a["areas"].startswith("Las potenciales áreas de afectación"))
        # sin fin no se vuelve a pedir cada hora (la vista usa fin_dia)
        self.correr(conn, lista=_lista(_fila(8000, vigente=True)))
        self.assertEqual(self.web.pedidos, [sh.LISTA_URL])

    def test_hoy_es_el_de_lima(self):
        # 03:00 UTC del 04-10 son las 22:00 del 03-10 en Lima: la purga cuenta desde el 03-10
        conn, _ = self.correr(ahora=datetime(2026, 10, 4, 3, 0, tzinfo=timezone.utc))
        self.assertEqual(conn.params(tarea.SQL_PURGA), [(date(2026, 10, 3) - timedelta(days=400),)])

    def test_latido_tiene_sus_claves(self):
        _, resumen = self.correr()
        self.assertEqual(list(resumen), ["filas", "vigentes", "vigilados", "detalles", "purgados", "fallas",
                                         "avisos", "atribucion"])
        _, resumen = self.correr(_Conexion(migrada=False))
        self.assertEqual(list(resumen), ["filas", "vigentes", "vigilados", "detalles", "purgados", "fallas",
                                         "avisos", "atribucion"])


class TestSql(unittest.TestCase):
    def test_upsert_no_pisa_el_detalle(self):
        sql = " ".join(tarea.SQL_AVISO.split())
        self.assertIn("on conflict (ca) do update set", sql)
        self.assertIn("visto_en = now()", sql)
        actualiza = sql.split("do update set", 1)[1]
        for col in ("emision", "inicio =", "fin =", "valor", "unidad", "umbral_rojo", "areas", "significado_rojo"):
            self.assertNotIn(col, actualiza)

    def test_candado_y_vigentes(self):
        self.assertEqual(tarea.SQL_CANDADO, "select pg_advisory_xact_lock(hashtext('rios'))")
        self.assertIn("not (ca = any(%s::int[]))", tarea.SQL_NO_VIGENTES)
        self.assertEqual(tarea.SQL_PURGA, "delete from aviso_hidrologico where fin_dia < %s")

    def test_hay_tabla_mira_las_dos(self):
        self.assertIn("to_regclass('public.aviso_hidrologico') is not null", tarea.SQL_HAY_TABLA)
        self.assertIn("to_regclass('public.rio_vigilado') is not null", tarea.SQL_HAY_TABLA)

    def test_nivel_sin_pisar(self):
        aviso = " ".join(tarea.SQL_AVISO.split())
        self.assertIn("nivel = coalesce(excluded.nivel, aviso_hidrologico.nivel)", aviso)
        detalle = " ".join(tarea.SQL_DETALLE.split())
        self.assertIn("nivel = coalesce(nivel, %(nivel)s)", detalle)
        self.assertIn("(fin at time zone 'America/Lima')::date, nivel", tarea.SQL_CON_DETALLE)


if __name__ == "__main__":
    unittest.main()
