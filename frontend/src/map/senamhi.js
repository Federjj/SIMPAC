import L from "leaflet";

// Servicios de mapas de SENAMHI (GeoServer de IDESEP). Se piden directo desde el navegador
// como imágenes WMS; si el servidor no responde (es intermitente), la capa avisa.
export const GEOSERVER = "https://idesep.senamhi.gob.pe/geoserver";

// Leyenda literal que piden los términos de uso de SENAMHI en todo soporte
// (https://www.senamhi.gob.pe/?p=terminos-condiciones). El panel de capas la muestra entera;
// en la barra del mapa va la versión corta.
export const ATRIBUCION_SENAMHI =
  "Información recopilada y trabajada por el Servicio Nacional de Meteorología e Hidrología del Perú. " +
  "El uso que se le da a esta información es de mi (nuestra) entera responsabilidad.";
export const FUENTE_SENAMHI = "Datos: SENAMHI";

// Estilo propio (SLD) para una capa ráster de lluvia en mm: transparente bajo el primer
// corte (el estilo oficial pinta de blanco opaco lo casi seco) y una escala de azules.
export function sldLluvia(capa, cortes) {
  const [c1, c2, c3, c4] = cortes;
  const e = (color, q, op) => `<ColorMapEntry color="${color}" quantity="${q}" opacity="${op}"/>`;
  return (
    '<StyledLayerDescriptor version="1.0.0" xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc">' +
    `<NamedLayer><Name>${capa}</Name><UserStyle><FeatureTypeStyle><Rule><RasterSymbolizer><ColorMap type="intervals">` +
    e("#000000", c1, 0) + e("#95CEF4", c2, 0.6) + e("#3BA5EB", c3, 0.65) + e("#3B3BEB", c4, 0.7) + e("#7B2FBE", 100000, 0.75) +
    "</ColorMap></RasterSymbolizer></Rule></FeatureTypeStyle></UserStyle></NamedLayer></StyledLayerDescriptor>"
  );
}

// Estilo propio para una capa de polígonos con un campo de nivel entero (2, 3, 4). Lleva borde
// del mismo color: las microcuencas son chicas y sin borde no se ven con el mapa alejado.
export function sldNiveles(capa, campo, colores) {
  const regla = (v, color) =>
    `<Rule><ogc:Filter><ogc:PropertyIsEqualTo><ogc:PropertyName>${campo}</ogc:PropertyName><ogc:Literal>${v}</ogc:Literal></ogc:PropertyIsEqualTo></ogc:Filter>` +
    `<PolygonSymbolizer><Fill><CssParameter name="fill">${color}</CssParameter><CssParameter name="fill-opacity">0.6</CssParameter></Fill>` +
    `<Stroke><CssParameter name="stroke">${color}</CssParameter><CssParameter name="stroke-width">1.5</CssParameter></Stroke></PolygonSymbolizer></Rule>`;
  return (
    '<StyledLayerDescriptor version="1.0.0" xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc">' +
    `<NamedLayer><Name>${capa}</Name><UserStyle><FeatureTypeStyle>` +
    Object.entries(colores).map(([v, c]) => regla(v, c)).join("") +
    "</FeatureTypeStyle></UserStyle></NamedLayer></StyledLayerDescriptor>"
  );
}

// Capa WMS de SENAMHI. Tras cada tanda de imágenes (al mover o acercar el mapa), `avisar`
// recibe el aviso de error si alguna falló, o `nota` si todas cargaron.
export function wmsSenamhi(espacio, capa, extra, { avisar, nota } = {}) {
  const t = L.tileLayer.wms(`${GEOSERVER}/${espacio}/wms`, {
    layers: capa,
    styles: "",
    format: "image/png",
    transparent: true,
    zIndex: 5,
    attribution: FUENTE_SENAMHI,
    ...extra,
  });
  let errores = 0;
  t.on("loading", () => {
    errores = 0;
  });
  t.on("tileerror", () => {
    errores++;
  });
  t.on("load", () =>
    avisar?.(errores ? "El servidor de mapas de SENAMHI no responde ahora; la capa puede verse incompleta." : nota)
  );
  return t;
}
