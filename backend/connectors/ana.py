"""
Conector ANA (Autoridad Nacional del Agua) — caudales de ríos en tiempo real.

Fuente: reporte nacional de caudales del Observatorio (ONRH), actualizado por hora.
  POST https://snirh.ana.gob.pe/onrh/ServicioReportes.asmx/ReporteNacionalCaudal
  payload: {pTipoRPT:1, pFecha:"dd/mm/aaaa", pCodAAA:"00", pCodALA:"00", pCodUbigeo:"00"}
           ("00" = todos)

Cada estación trae su propio umbral de ALERTA y de EMERGENCIA, así que el estado
de riesgo se calcula directamente comparando VALOR contra esos umbrales.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from . import _http

URL = "https://snirh.ana.gob.pe/onrh/ServicioReportes.asmx/ReporteNacionalCaudal"


@dataclass
class EstacionCaudal:
    estacion: str
    rio: str
    departamento: str
    provincia: str
    distrito: str
    operador: str
    valor: float | None
    unidad: str
    umbral_alerta: float | None
    umbral_emergencia: float | None
    tendencia: str
    hora: str
    lat: float | None
    lon: float | None

    @property
    def estado(self) -> str:
        """normal | alerta | emergencia | s.d. (sin umbral o sin dato)."""
        if self.valor is None or self.umbral_alerta is None:
            return "s.d."
        if self.umbral_emergencia is not None and self.valor >= self.umbral_emergencia:
            return "emergencia"
        if self.valor >= self.umbral_alerta:
            return "alerta"
        return "normal"


def _num(s) -> float | None:
    if s is None:
        return None
    s = str(s).strip()
    if s == "" or s.lower() in ("s.d.", "sd", "n.d.", "nd", "null"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def reporte_caudal(fecha: date | None = None) -> list[EstacionCaudal]:
    """Reporte nacional de caudales (todas las estaciones) para una fecha."""
    f = (fecha or date.today()).strftime("%d/%m/%Y")
    body = f'{{pTipoRPT:1, pFecha:"{f}",pCodAAA:"00",pCodALA:"00",pCodUbigeo:"00"}}'
    filas = _http.post_json(URL, body) or []
    out: list[EstacionCaudal] = []
    for r in filas:
        out.append(EstacionCaudal(
            estacion=str(r.get("ESTACION", "")).strip(),
            rio=str(r.get("RIO", "")).strip(),
            departamento=str(r.get("DEPARTAMENTO", "")).strip(),
            provincia=str(r.get("PROVINCIA", "")).strip(),
            distrito=str(r.get("DISTRITO", "")).strip(),
            operador=str(r.get("OPERADOR", "")).strip(),
            valor=_num(r.get("VALOR")),
            unidad=str(r.get("UNIDADMEDIDA", "")).strip(),
            umbral_alerta=_num(r.get("UALERTA")),
            umbral_emergencia=_num(r.get("UEMERGENCIA")),
            tendencia=str(r.get("TENDENCIA", "")).strip(),
            hora=str(r.get("HORA", "")).strip(),
            lat=_num(r.get("LATITUD")),
            lon=_num(r.get("LONGITUD")),
        ))
    return out


def caudal_cajamarca(fecha: date | None = None) -> list[EstacionCaudal]:
    return [e for e in reporte_caudal(fecha) if e.departamento.upper() == "CAJAMARCA"]


def en_alerta(fecha: date | None = None) -> list[EstacionCaudal]:
    """Estaciones cuyo caudal ya superó su umbral de alerta o emergencia."""
    return [e for e in reporte_caudal(fecha) if e.estado in ("alerta", "emergencia")]
