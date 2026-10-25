// Mapas de eventos El Niño pasados (tabla mapa, variable 'FEN'): qué eventos y trimestres hay, cómo
// se nombra cada opción del selector y cómo se migra un valor viejo. Puro: sin React ni Leaflet, así
// se prueba con `node --test` (fen.test.js) y lo comparten la capa (map/layers/fenHistorico.js), la
// consulta (lib/queries.js) y el panel El Niño (components/ElNinoPanel.jsx).
//
// SENAMHI publica cada evento en trimestres (DEF = diciembre a febrero, EFM = enero a marzo, FMA =
// febrero a abril); el cargador backend/mapas/cargar_fen.py guarda una fila por evento y trimestre,
// con `periodo` el evento ("1997-1998"), `trimestre` el código ("DEF") y `meses` el texto legible
// ("diciembre de 1997 a febrero de 1998"). Aquí la lista es fija (como el resto del contrato de
// capas): si el cargador suma un trimestre o un evento, se agrega a EVENTOS_FEN.
//
// El valor de la opción es "<periodo>|<trimestre>" ("1997-1998|DEF"). Hasta el 24-10-2026 era solo
// el periodo ("1997-1998"): migrarValorFEN lo lleva al primer trimestre del evento para que las
// capas recordadas (lib/preferencias.js) sigan funcionando.

export const TRIMESTRES = [
  { codigo: "DEF", corto: "dic a feb" },
  { codigo: "EFM", corto: "ene a mar" },
  { codigo: "FMA", corto: "feb a abr" },
];

// En el orden del selector; `trimestres` en el orden en que se ofrecen (el verano primero). Son
// los que trae la BD el 25-10-2026 (13 filas): 1982-83, 1997-98 y 2017 con tres, 2023 y 2023-24 con dos.
export const EVENTOS_FEN = [
  { periodo: "1982-1983", nombre: "El Niño 1982-1983", trimestres: ["DEF", "EFM", "FMA"] },
  { periodo: "1997-1998", nombre: "El Niño 1997-1998", trimestres: ["DEF", "EFM", "FMA"] },
  { periodo: "2017", nombre: "El Niño costero 2017", trimestres: ["DEF", "EFM", "FMA"] },
  { periodo: "2023", nombre: "El Niño costero 2023", trimestres: ["EFM", "FMA"] },
  { periodo: "2023-2024", nombre: "El Niño 2023-2024", trimestres: ["DEF", "EFM"] },
];

export const SEPARADOR = "|";
export const DEFECTO_FEN = "1997-1998|DEF";

export const valorFEN = (periodo, trimestre) => `${periodo}${SEPARADOR}${trimestre}`;

// "1997-1998|DEF" -> { periodo: "1997-1998", trimestre: "DEF" }; sin trimestre -> trimestre null.
export function partirFEN(valor) {
  const [periodo, trimestre] = String(valor ?? "").split(SEPARADOR);
  return { periodo: periodo || null, trimestre: trimestre || null };
}

export const eventoFEN = (periodo) => EVENTOS_FEN.find((e) => e.periodo === periodo) ?? null;

// "dic a feb" (o el código si no se conoce)
export const mesesCortos = (trimestre) => TRIMESTRES.find((t) => t.codigo === trimestre)?.corto ?? trimestre;

// "El Niño 1997-1998, dic a feb"
export function etiquetaFEN(periodo, trimestre) {
  const nombre = eventoFEN(periodo)?.nombre ?? `El Niño ${periodo}`;
  return trimestre ? `${nombre}, ${mesesCortos(trimestre)}` : nombre;
}

// Opciones del selector "Evento": una por evento y trimestre, en el orden de EVENTOS_FEN y de sus
// trimestres (el verano primero).
export const OPCIONES_FEN = EVENTOS_FEN.flatMap((e) =>
  e.trimestres.map((t) => ({ valor: valorFEN(e.periodo, t), etiqueta: etiquetaFEN(e.periodo, t), periodo: e.periodo, trimestre: t }))
);

export const esValorFEN = (valor) => OPCIONES_FEN.some((o) => o.valor === valor);

// Valor viejo ("1997-1998", solo el evento) -> el primer trimestre de ese evento ("1997-1998|DEF").
// Un valor ya nuevo o desconocido vuelve igual (preferencias.js lo descarta si no existe).
export function migrarValorFEN(valor) {
  if (typeof valor !== "string" || valor.includes(SEPARADOR)) return valor;
  const e = eventoFEN(valor);
  return e ? valorFEN(e.periodo, e.trimestres[0]) : valor;
}
