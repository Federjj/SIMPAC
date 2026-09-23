"""
Serie mensual del ICEN (tabla icen_serie): la regla de precedencia ENFEN > IGP probada de
verdad sobre sqlite3 (entiende el mismo INSERT ... ON CONFLICT DO UPDATE ... WHERE, con
IS DISTINCT FROM sobre filas), el recorte de la serie del IGP, cuántos meses escritos
cuenta el latido y cómo la tarea enfen decide qué es "lo leído" y cuándo releer el informe
vigente para llenar la serie.

  SQL_ICEN_SERIE: el ENFEN pisa lo que haya; el IGP solo completa meses sin dato del ENFEN
                  y corrige los suyos; si nada cambió, la fila no se toca (ni cuenta en el
                  rowcount del executemany, que es lo que dice el latido).

La categoría de los meses del IGP la calcula SIMPAC (igp.categoria); la de los del ENFEN es
la oficial de la tabla de su informe. Los datos de la prueba de punta a punta son los reales
del 22-09-2026: ICEN.txt del IGP (último mes 2026-05) y la Tabla 3 del Informe Técnico ENFEN
N° 16 (2025-08 a 2026-07). Sin Postgres ni red: solo librería estándar.
"""
import itertools
import logging
import sqlite3
import unittest
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from unittest import mock

from backend.connectors import enfen, igp
from backend.connectors.senamhi import HORA_PERU
from backend.ingesta import enfen as tarea
from backend.ingesta import guardar as guardar_mod
from backend.ingesta.guardar import SQL_HAY_ICEN_SERIE, SQL_ICEN_SERIE, filas_serie
from backend.ingesta.recolectar import MESES_SERIE_IGP, Pasada, serie_icen_igp

# Misma forma que supabase/migrations/20260923012354_icen_serie.sql (tipos y checks de sqlite).
TABLA = """
create table icen_serie (
  mes        text primary key check (mes glob '[0-9][0-9][0-9][0-9]-[01][0-9]'),
  valor      double precision not null,
  categoria  text not null,
  origen     text not null check (origen in ('IGP', 'ENFEN')),
  ts_captura text not null default (now())
)
"""

# ICEN.txt del IGP, últimos 36 meses (2023-06 a 2026-05), leído el 22-09-2026.
IGP_REAL = [
    2.57, 2.92, 2.9, 2.68, 2.28, 2.01, 1.67,                                  # 2023-06 .. 2023-12
    1.34, 0.88, 0.38, -0.38, -0.78, -0.97, -0.72, -0.65, -0.5, -0.34, -0.1, -0.11,   # 2024
    0.0, 0.45, 0.72, 0.46, 0.18, 0.11, 0.17, -0.01, -0.22, -0.42, -0.5, -0.51,       # 2025
    -0.06, 0.42, 0.96, 1.34, 1.98,                                            # 2026-01 .. 2026-05
]
# Tabla 3 del Informe Técnico ENFEN N° 16 (11-09-2026), tal como la devuelve el conector.
ENFEN_IT16 = [
    ("2025-08", -0.01, "Neutra"), ("2025-09", -0.22, "Neutra"), ("2025-10", -0.42, "Neutra"),
    ("2025-11", -0.5, "Neutra"), ("2025-12", -0.51, "Neutra"), ("2026-01", -0.06, "Neutra"),
    ("2026-02", 0.42, "Neutra"), ("2026-03", 0.96, "Cálida débil"), ("2026-04", 1.34, "Cálida moderada"),
    ("2026-05", 1.98, "Cálida moderada"), ("2026-06", 2.66, "Cálida fuerte"), ("2026-07", 3.38, "Cálida fuerte"),
]


HOY_22_09 = datetime(2026, 9, 22, 12, tzinfo=HORA_PERU)   # el ICEN.txt puede llegar hasta 2026-08


def _mes(k: int) -> str:
    return f"{k // 12}-{k % 12 + 1:02d}"


def _puntos_igp(desde=(2023, 6), valores=IGP_REAL) -> list[igp.PuntoICEN]:
    k0 = desde[0] * 12 + desde[1] - 1
    return [igp.PuntoICEN((k0 + i) // 12, (k0 + i) % 12 + 1, v) for i, v in enumerate(valores)]


def _filas_igp(puntos) -> list[tuple]:
    """Lo mismo que guardar() arma para icen_serie a partir de la Pasada."""
    return filas_serie([(f"{p.anio}-{p.mes:02d}", p.valor, p.categoria) for p in puntos], "IGP")


class _Base(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.addCleanup(self.conn.close)
        reloj = itertools.count(1)   # now() distinto en cada llamada: se ve si la fila se tocó
        self.conn.create_function("now", 0, lambda: f"t{next(reloj):04d}")
        self.conn.execute(TABLA)

    def escribir(self, filas):
        self.assertEqual(SQL_ICEN_SERIE.count("%s"), 4)
        self.conn.executemany(SQL_ICEN_SERIE.replace("%s", "?"), filas)

    def una(self, mes, valor, origen, categoria="Cálida fuerte"):
        self.escribir([(mes, valor, categoria, origen)])

    def fila(self, mes):
        return self.conn.execute(
            "select valor, categoria, origen, ts_captura from icen_serie where mes = ?", (mes,)).fetchone()

    def tabla(self):
        return self.conn.execute("select mes, valor, categoria, origen from icen_serie order by mes").fetchall()


class TestPrecedencia(_Base):
    def test_tabla_vacia_inserta_de_cualquier_origen(self):
        self.una("2026-05", 1.98, "IGP", "Cálida moderada")
        self.una("2026-07", 3.38, "ENFEN")
        self.assertEqual(self.tabla(), [("2026-05", 1.98, "Cálida moderada", "IGP"),
                                        ("2026-07", 3.38, "Cálida fuerte", "ENFEN")])

    def test_enfen_pisa_al_igp(self):
        self.una("2026-05", 1.97, "IGP", "Cálida moderada")
        self.una("2026-05", 1.98, "ENFEN", "Cálida moderada")
        self.assertEqual(self.fila("2026-05")[:3], (1.98, "Cálida moderada", "ENFEN"))

    def test_igp_nunca_pisa_al_enfen(self):
        self.una("2026-05", 1.98, "ENFEN", "Cálida moderada")
        antes = self.fila("2026-05")
        self.una("2026-05", 1.90, "IGP", "Cálida moderada")   # otro valor: igual no gana
        self.una("2026-05", 1.98, "IGP", "Cálida moderada")   # mismo valor: tampoco cambia el origen
        self.assertEqual(self.fila("2026-05"), antes)         # ni el ts_captura

    def test_igp_completa_los_meses_que_el_enfen_no_tiene(self):
        self.una("2026-05", 1.98, "ENFEN", "Cálida moderada")
        self.escribir([("2026-03", 0.96, "Cálida débil", "IGP"), ("2026-04", 1.34, "Cálida moderada", "IGP"),
                       ("2026-05", 1.50, "Cálida moderada", "IGP")])
        self.assertEqual([(m, o) for m, _, _, o in self.tabla()],
                         [("2026-03", "IGP"), ("2026-04", "IGP"), ("2026-05", "ENFEN")])
        self.assertEqual(self.fila("2026-05")[0], 1.98)

    def test_igp_corrige_sus_propios_meses(self):
        self.una("2026-04", 1.30, "IGP", "Cálida débil")
        self.una("2026-04", 1.34, "IGP", "Cálida moderada")
        self.assertEqual(self.fila("2026-04")[:3], (1.34, "Cálida moderada", "IGP"))

    def test_un_informe_nuevo_corrige_al_anterior(self):
        self.una("2026-06", 2.60, "ENFEN")
        self.una("2026-06", 2.66, "ENFEN")
        self.assertEqual(self.fila("2026-06")[:3], (2.66, "Cálida fuerte", "ENFEN"))

    def test_sin_cambios_la_fila_no_se_toca(self):
        # la ingesta reenvía 36 meses cada hora: no se reescriben si son iguales
        self.una("2026-05", 1.98, "IGP", "Cálida moderada")
        self.una("2026-06", 2.66, "ENFEN")
        antes = self.tabla(), self.fila("2026-05"), self.fila("2026-06")
        self.una("2026-05", 1.98, "IGP", "Cálida moderada")
        self.una("2026-06", 2.66, "ENFEN")
        self.assertEqual((self.tabla(), self.fila("2026-05"), self.fila("2026-06")), antes)

    def test_cambio_de_categoria_con_el_mismo_valor_se_guarda(self):
        # p. ej. si se corrigen los cortes de categoría: el valor igual, la categoría no
        self.una("2026-05", 1.98, "IGP", "Cálida fuerte")
        self.una("2026-05", 1.98, "IGP", "Cálida moderada")
        self.assertEqual(self.fila("2026-05")[1], "Cálida moderada")

    def test_el_orden_de_llegada_no_importa(self):
        # Cualquier intercalado de escrituras deja: el último valor del ENFEN si hubo alguno;
        # si no, el último del IGP.
        ops = [("IGP", 1.90), ("IGP", 1.95), ("ENFEN", 1.98), ("ENFEN", 2.01)]
        for orden in itertools.permutations(ops):
            with self.subTest(orden=orden):
                self.conn.execute("delete from icen_serie")
                for origen, valor in orden:
                    self.una("2026-05", valor, origen)
                enfen_ = [v for o, v in orden if o == "ENFEN"]
                self.assertEqual(self.fila("2026-05")[:3:2], (enfen_[-1], "ENFEN"))
        for orden in itertools.permutations(ops[:2]):   # solo IGP
            with self.subTest(orden=orden):
                self.conn.execute("delete from icen_serie")
                for origen, valor in orden:
                    self.una("2026-05", valor, origen)
                self.assertEqual(self.fila("2026-05")[:3:2], (orden[-1][1], "IGP"))


class TestSerieReal(_Base):
    """Punta a punta con los datos del 22-09-2026: qué queda en icen_serie."""

    def esperado(self):
        # 2023-06 a 2025-07 del IGP (26 meses) y 2025-08 a 2026-07 del ENFEN (12)
        igp_ = [(f, v, c, o) for f, v, c, o in _filas_igp(_puntos_igp()) if f < "2025-08"]
        return igp_ + filas_serie(ENFEN_IT16, "ENFEN")

    def test_ingesta_y_enfen_en_cualquier_orden(self):
        igp_filas = _filas_igp(serie_icen_igp(_puntos_igp((1950, 1), [0.0] * 881 + IGP_REAL))[0])
        self.assertEqual(len(igp_filas), MESES_SERIE_IGP)
        enfen_filas = filas_serie(ENFEN_IT16, "ENFEN")
        for orden in ((igp_filas, enfen_filas), (enfen_filas, igp_filas), (igp_filas, enfen_filas, igp_filas)):
            with self.subTest(primero=orden[0][0][3], pasos=len(orden)):
                self.conn.execute("delete from icen_serie")
                for filas in orden:
                    self.escribir(filas)
                self.assertEqual(self.tabla(), self.esperado())

    def test_ultimos_24_meses_para_el_grafico(self):
        self.escribir(_filas_igp(_puntos_igp()))
        self.escribir(filas_serie(ENFEN_IT16, "ENFEN"))
        ultimos = self.conn.execute(
            "select mes, origen from (select * from icen_serie order by mes desc limit 24) order by mes").fetchall()
        self.assertEqual((ultimos[0][0], ultimos[-1][0]), ("2024-08", "2026-07"))
        self.assertEqual(sum(o == "ENFEN" for _, o in ultimos), 12)
        self.assertEqual(sum(o == "IGP" for _, o in ultimos), 12)
        # el mes más nuevo es el del ENFEN (el IGP no publica desde mayo)
        self.assertEqual(self.tabla()[-1], ("2026-07", 3.38, "Cálida fuerte", "ENFEN"))


class TestSerieIGP(unittest.TestCase):
    def test_ultimos_36_meses_por_calendario(self):
        serie, descartadas = serie_icen_igp(_puntos_igp((2020, 1), [0.1] * 77))   # 2020-01 .. 2026-05
        self.assertEqual(descartadas, 0)
        self.assertEqual(len(serie), 36)
        self.assertEqual(((serie[0].anio, serie[0].mes), (serie[-1].anio, serie[-1].mes)), ((2023, 6), (2026, 5)))

    def test_hueco_en_el_archivo_no_estira_la_ventana(self):
        # falta 2025 entero: la ventana sigue siendo 36 meses de calendario, no 36 filas
        puntos = [p for p in _puntos_igp((2020, 1), [0.1] * 77) if p.anio != 2025]
        serie, _ = serie_icen_igp(puntos)
        self.assertEqual((serie[0].anio, serie[0].mes), (2023, 6))
        self.assertEqual(len(serie), 24)

    def test_mes_repetido_vale_la_ultima_fila_y_queda_en_orden(self):
        puntos = [igp.PuntoICEN(2026, 5, 1.98), igp.PuntoICEN(2026, 4, 1.34), igp.PuntoICEN(2026, 5, 2.00)]
        serie, _ = serie_icen_igp(puntos)
        self.assertEqual([(p.mes, p.valor) for p in serie], [(4, 1.34), (5, 2.00)])

    def test_filas_imposibles(self):
        malos = [igp.PuntoICEN(2026, 0, 1.0), igp.PuntoICEN(2026, 13, 1.0), igp.PuntoICEN(26, 5, 1.0),
                 igp.PuntoICEN(2026, 5, float("inf")), igp.PuntoICEN(2026, 5, -12.0)]
        self.assertEqual(serie_icen_igp(malos), ([], 5))
        self.assertEqual(serie_icen_igp([]), ([], 0))

    def test_categoria_de_la_nota_tecnica_2024(self):
        # la de los meses del IGP la calcula SIMPAC: el ICEN.txt no trae categoría
        filas = _filas_igp([igp.PuntoICEN(2026, 5, 1.98), igp.PuntoICEN(2024, 6, -0.97)])
        self.assertEqual(filas, [("2024-06", -0.97, "Fría", "IGP"), ("2026-05", 1.98, "Cálida moderada", "IGP")])

    def test_mes_futuro_se_descarta_y_no_corre_la_ventana(self):
        real, _ = serie_icen_igp(_puntos_igp(), ahora=HOY_22_09)
        for fila in (igp.PuntoICEN(2099, 1, 0.3), igp.PuntoICEN(2026, 12, 0.3)):
            with self.subTest(fila=fila):
                # antes: con 2099-01 la serie era solo [2099-01]; con 2026-12 empezaba en 2024-01
                serie, descartadas = serie_icen_igp(_puntos_igp() + [fila], ahora=HOY_22_09)
                self.assertEqual((serie, descartadas), (real, 1))
                self.assertEqual(((serie[0].anio, serie[0].mes), (serie[-1].anio, serie[-1].mes)),
                                 ((2023, 6), (2026, 5)))

    def test_tope_es_el_mes_anterior_al_actual_en_hora_de_peru(self):
        puntos = [igp.PuntoICEN(2026, 7, 3.38), igp.PuntoICEN(2026, 8, 3.7), igp.PuntoICEN(2026, 9, 3.8)]
        casos = {
            HOY_22_09: (8, 1),
            # 03:00 UTC del 1-oct son las 22:00 del 30-set en Lima: setiembre sigue siendo futuro
            datetime(2026, 10, 1, 3, 0, tzinfo=timezone.utc): (8, 1),
            datetime(2026, 10, 1, 6, 0, tzinfo=timezone.utc): (9, 0),   # ya es octubre en Lima
        }
        for ahora, (ultimo, descartadas) in casos.items():
            with self.subTest(ahora=ahora):
                serie, n = serie_icen_igp(puntos, ahora=ahora)
                self.assertEqual((serie[-1].mes, n), (ultimo, descartadas))

    def test_tope_en_enero_es_diciembre_del_anio_anterior(self):
        enero = datetime(2027, 1, 15, 12, tzinfo=HORA_PERU)
        self.assertEqual(igp.ultimo_mes_posible(enero), (2026, 12))
        serie, n = serie_icen_igp([igp.PuntoICEN(2026, 12, 1.0), igp.PuntoICEN(2027, 1, 1.1)], ahora=enero)
        self.assertEqual(([(p.anio, p.mes) for p in serie], n), ([(2026, 12)], 1))

    def test_ultimo_del_igp_tampoco_es_un_mes_futuro(self):
        # igp.ultimo() (lo usa el prototipo) tenía el mismo problema que la serie
        with mock.patch.object(igp, "icen", return_value=_puntos_igp() + [igp.PuntoICEN(2099, 1, 0.3)]):
            p = igp.ultimo(HOY_22_09)
            self.assertEqual((p.anio, p.mes, p.valor), (2026, 5, 1.98))
        with mock.patch.object(igp, "icen", return_value=[igp.PuntoICEN(2099, 1, 0.3)]):
            self.assertIsNone(igp.ultimo(HOY_22_09))


URL_A = "https://www.senamhi.gob.pe/load/file/02273SENA-55.pdf"
URL_B = "https://cdn.www.gob.pe/uploads/document/file/9000001/IT-16-2026.pdf"


class TestRelectura(unittest.TestCase):
    """Qué queda como "leído" tras releer el informe vigente para llenar la serie."""

    def ref(self, url, publicado=None, fecha=None, numero=None, alias=()):
        return enfen.ReferenciaInforme(url=url, publicado=publicado, numero=numero, fecha=fecha, alias=list(alias))

    def test_misma_url(self):
        leido = self.ref(URL_A, date(2026, 9, 14))
        nuevo = self.ref(URL_A, date(2026, 9, 14), date(2026, 9, 11), 16)
        self.assertEqual(tarea._tras_relectura(nuevo, leido), (nuevo, False))   # gana número y portada

    def test_otra_url_del_mismo_informe(self):
        leido = self.ref(URL_A, date(2026, 9, 14), alias=["https://www.senamhi.gob.pe/viejo.pdf"])
        nuevo = self.ref(URL_B, date(2026, 9, 17), date(2026, 9, 11), 16)
        ref, viejo = tarea._tras_relectura(nuevo, leido)
        self.assertFalse(viejo)
        self.assertEqual((ref.url, ref.publicado, ref.numero), (URL_B, date(2026, 9, 17), 16))
        self.assertEqual(ref.alias, sorted([URL_A, "https://www.senamhi.gob.pe/viejo.pdf"]))

    def test_por_portada(self):
        leido = self.ref(URL_A, date(2026, 9, 14), date(2026, 9, 11), 16)
        self.assertEqual(tarea._frente(self.ref(URL_B, date(2026, 9, 30), date(2026, 9, 11)), leido), "mismo")
        self.assertEqual(tarea._frente(self.ref(URL_B, date(2026, 9, 15), date(2026, 9, 25)), leido), "nuevo")
        self.assertEqual(tarea._frente(self.ref(URL_B, date(2026, 9, 15), date(2026, 8, 26)), leido), "viejo")

    def test_por_fecha_de_publicacion(self):
        leido = self.ref(URL_A, date(2026, 9, 14))
        self.assertEqual(tarea._frente(self.ref(URL_B, date(2026, 9, 10)), leido), "mismo")   # margen 4 días
        self.assertEqual(tarea._frente(self.ref(URL_B, date(2026, 9, 28)), leido), "nuevo")
        self.assertEqual(tarea._frente(self.ref(URL_B, date(2026, 8, 28)), leido), "viejo")

    def test_sin_fechas_no_se_puede_saber(self):
        self.assertEqual(tarea._frente(self.ref(URL_B), self.ref(URL_A, date(2026, 9, 14))), "nuevo")

    def test_uno_mas_viejo_no_reemplaza_lo_leido(self):
        leido = self.ref(URL_A, date(2026, 9, 14), date(2026, 9, 11), 16)
        self.assertEqual(tarea._tras_relectura(self.ref(URL_B, date(2026, 8, 28), date(2026, 8, 26), 15), leido),
                         (leido, True))

    def test_cuando_se_relee(self):
        # serie sin meses del ENFEN, o marca serie_pendiente (la relectura halló uno más
        # viejo) con más de 24 h; nunca sin informe leído ni sin la tabla
        ahora = datetime(2026, 9, 22, 18, tzinfo=timezone.utc)
        leido = self.ref(URL_A, date(2026, 9, 14))

        def marca(horas):
            return enfen.ReferenciaInforme(url=URL_B, publicado=date(2026, 8, 28),
                                           ts=None if horas is None else ahora - timedelta(hours=horas))

        casos = [
            ((leido, 0, None), True), ((leido, 12, None), False),
            ((None, 0, None), False), ((leido, None, None), False),
            ((leido, 12, marca(6)), False), ((leido, 0, marca(6)), False),   # como mucho cada 24 h
            ((leido, 12, marca(24)), True), ((leido, 12, marca(25)), True),
            ((leido, 12, marca(None)), True),   # marca sin hora (latido dañado): se relee
            ((leido, 12, marca(-1)), True),     # hora en el futuro: no se espera, como el fallido
            ((leido, None, marca(25)), False),
        ]
        for (leido_, meses, pendiente), esperado in casos:
            with self.subTest(leido=leido_ is not None, meses=meses, pendiente=pendiente and pendiente.ts):
                self.assertIs(tarea._releer(leido_, meses, pendiente, ahora), esperado)


class _CursorSqlite:
    """Cursor tipo psycopg sobre la tabla sqlite: solo lo que guardar() y la tarea enfen hacen con icen_serie."""

    def __init__(self, db):
        self.db, self.fila, self.rowcount = db, None, -1

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        if sql == SQL_HAY_ICEN_SERIE:
            self.fila = (True,)
        elif sql == tarea.SQL_MESES_SERIE:
            self.fila = self.db.execute(sql.replace("%s", "?"), params).fetchone()
        elif sql == tarea.SQL_LATIDO_PREVIO:
            self.fila = None   # sin latido previo
        # el resto (indice, comunicado, latido) no toca icen_serie

    def executemany(self, sql, filas):
        assert sql == SQL_ICEN_SERIE, sql
        # sqlite, como psycopg, suma en rowcount las filas afectadas de todo el executemany
        self.rowcount = self.db.executemany(sql.replace("%s", "?"), filas).rowcount

    def fetchone(self):
        return self.fila


class TestLatidoCuentaEscritos(_Base):
    """El campo icen_serie de los latidos: meses escritos (insertados o cambiados), no enviados."""

    def setUp(self):
        super().setUp()
        logging.disable(logging.CRITICAL)   # la tarea enfen avisa que el comunicado (simulado) falló
        self.addCleanup(logging.disable, logging.NOTSET)

    @contextmanager
    def conectar(self):
        yield mock.Mock(cursor=lambda: _CursorSqlite(self.conn))

    def ingesta(self, puntos):
        with mock.patch.object(guardar_mod, "conectar", self.conectar):
            return guardar_mod.guardar(Pasada(icen_serie=puntos))["icen_serie"]

    def tarea_enfen(self, meses):
        ref = enfen.ReferenciaInforme(url=URL_A, publicado=date(2026, 9, 14), numero=16, fecha=date(2026, 9, 11))
        informe = enfen.InformeICEN(url=URL_A, numero=16, fecha=date(2026, 9, 11), icen=meses, icen_tmp=None)
        with mock.patch.object(tarea, "conectar", self.conectar), \
             mock.patch.object(enfen, "ultimo_comunicado", side_effect=RuntimeError("sin red")), \
             mock.patch.object(enfen, "informe_tecnico_icen", return_value=enfen.ConsultaInforme(informe, ref)):
            return tarea.actualizar()["icen_serie"]

    def test_solo_cuentan_los_meses_insertados_o_cambiados(self):
        igp_ = _puntos_igp()
        self.assertEqual(self.ingesta(igp_), 36)       # tabla vacía: todos nuevos
        self.assertEqual(self.ingesta(igp_), 0)        # la hora siguiente, sin cambios (antes decía 36)
        self.assertEqual(self.tarea_enfen(ENFEN_IT16), 12)   # 10 pisan al IGP y 2 son nuevos
        self.assertEqual(self.tarea_enfen(ENFEN_IT16), 0)    # el mismo informe otra vez
        self.assertEqual(self.ingesta(igp_), 0)        # el IGP no pisa los meses del ENFEN
        corregido = [igp.PuntoICEN(p.anio, p.mes, round(p.valor + 0.05, 2)) if (p.anio, p.mes) == (2025, 7) else p
                     for p in igp_]
        self.assertEqual(self.ingesta(corregido), 1)   # el IGP corrige uno de sus meses
        self.assertEqual(len(self.tabla()), 38)


if __name__ == "__main__":
    unittest.main()
