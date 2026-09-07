"""
Conector SENAMHI — red de estaciones hidrometeorológicas.

Dos productos:
  1. inventario_estaciones(dp)  -> lista de estaciones de un departamento.
  2. datos_horarios(est)        -> serie horaria (precip/temp) de una estación,
                                   de las últimas ~48 h (tiempo real, sin CAPTCHA).

Origen de los datos (ver docs/README-tecnico.md):
  - Inventario:  https://www.senamhi.gob.pe/mapas/mapa-estaciones-2/?dp=<dp>
                 (array JS `PruebaTest` embebido en el HTML)
  - Serie:       https://www.senamhi.gob.pe/mapas/mapa-estaciones-2/map_red_graf.php
                 (config de Highcharts embebida en el HTML)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from . import _http

BASE = "https://www.senamhi.gob.pe/mapas/mapa-estaciones-2"


@dataclass
class Estacion:
    cod: str
    nombre: str
    lat: float
    lon: float
    tipo: str          # "M" meteorológica | "H" hidrológica
    categoria: str     # CO, PLU, EMA, EHA, MAP, HLG, ...
    estado: str        # REAL | DIFERIDO | AUTOMATICA
    cod_old: str = ""

    @property
    def es_automatica(self) -> bool:
        return self.estado == "AUTOMATICA"


@dataclass
class SerieHoraria:
    estacion: str
    codigo: str
    timestamps: list[str] = field(default_factory=list)   # "YYYY/MM/DD - HH"
    precip_mm: list[float | None] = field(default_factory=list)
    temp_c: list[float | None] = field(default_factory=list)

    @property
    def ultimo(self) -> dict | None:
        if not self.timestamps:
            return None
        return {
            "ts": self.timestamps[-1],
            "precip_mm": self.precip_mm[-1] if self.precip_mm else None,
            "temp_c": self.temp_c[-1] if self.temp_c else None,
        }

    def precip_acumulada(self, horas: int = 24) -> float:
        vals = [v for v in self.precip_mm[-horas:] if isinstance(v, (int, float))]
        return round(sum(vals), 2)


def inventario_estaciones(dp: str = "cajamarca") -> list[Estacion]:
    """Estaciones de un departamento (por defecto Cajamarca)."""
    html = _http.get(f"{BASE}/?dp={dp}")
    m = re.search(r"var\s+PruebaTest\s*=\s*(\[.*?\]);", html, re.S)
    if not m:
        raise RuntimeError("No se encontró el array PruebaTest en el HTML de SENAMHI")
    registros = json.loads(m.group(1))
    out: list[Estacion] = []
    for r in registros:
        out.append(Estacion(
            cod=str(r.get("cod", "")),
            nombre=str(r.get("nom", "")).strip(),
            lat=float(r["lat"]),
            lon=float(r["lon"]),
            tipo=str(r.get("ico", "")),
            categoria=str(r.get("cate", "")),
            estado=str(r.get("estado", "")),
            cod_old=str(r.get("cod_old", "")),
        ))
    return out


def _parse_num_array(texto: str) -> list[float | None]:
    vals: list[float | None] = []
    for tok in texto.split(","):
        tok = tok.strip()
        if not tok:
            continue
        vals.append(None if tok == "null" else float(tok))
    return vals


def _serie_por_nombre(html: str, palabra_clave: str) -> list[float | None]:
    m = re.search(
        r"name:\s*'[^']*" + re.escape(palabra_clave) + r"[^']*'.*?data:\s*\[([^\]]*)\]",
        html, re.S,
    )
    return _parse_num_array(m.group(1)) if m else []


def datos_horarios(est: Estacion) -> SerieHoraria:
    """Serie horaria (últimas ~48 h) de una estación. Gratis, sin CAPTCHA."""
    html = _http.get(
        f"{BASE}/map_red_graf.php",
        {
            "cod": est.cod,
            "estado": est.estado,
            "tipo_esta": est.tipo,
            "cate": est.categoria,
            "cod_old": est.cod_old,
        },
    )
    mcat = re.search(r"categories:\s*\[([^\]]+)\]", html)
    cats = re.findall(r"'([^']+)'", mcat.group(1)) if mcat else []
    return SerieHoraria(
        estacion=est.nombre,
        codigo=est.cod,
        timestamps=cats,
        precip_mm=_serie_por_nombre(html, "Precipitaci"),
        temp_c=_serie_por_nombre(html, "Temperatura"),
    )


def estaciones_automaticas(dp: str = "cajamarca") -> list[Estacion]:
    """Solo las estaciones con telemetría horaria (las útiles para alertas)."""
    return [e for e in inventario_estaciones(dp) if e.es_automatica]
