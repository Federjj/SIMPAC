import { useEffect, useMemo, useRef, useState } from "react";
import { getCaucesRios, getCaucesZonas, getCaudales, getSenalesCauces, getTitular, getZonasRio } from "@/lib/queries";
import { conSimulacion, simularCauce } from "@/lib/simulacion";
import { aligerar, zonasDeCauce } from "@/lib/cauces";
import {
  LEJOS_M,
  botonPrincipal,
  caudalDelRio,
  chipSinZonas,
  chipsDistancia,
  distancias,
  esFuerte,
  lineaFuentes,
  nivelMaximo,
  rioCercano,
  rioEnDepto,
  rioParaVer,
  rioPrincipal,
  riosTrazados,
  titularCorto,
} from "@/lib/zonaAhora";

const CADA_MS = 5 * 60_000;
const TITULAR_FRESCO_MS = 90 * 60_000; // la tarea 'titular' corre cada 30 min: tres vueltas sin correr es viejo
const TITULAR_MAX = 110; // más largo no cabe en 2 líneas: va como resumen en la altura completa

// Lo que la tarjeta "Tu zona ahora" necesita, calculado una vez por cambio de entrada (memo):
//   p         usePanorama(depto)         rios  useRiosVigilados(depto) ([{ rio, estado }])
//   userPos   [lat, lon] del GPS o null  porGps  si la zona salió del GPS
//   ciudad    la ciudad elegida (data/cities)   depto  departamento de la zona
// Devuelve { origen, porGps, nivel, titular, chips, boton, fuentes, principal, cercano, verRio, d,
// caudal, zonas, hayRios, hayTrazadosDepto, instruccion }. Las zonas del Mashcón (rio_zona_mapa),
// los caudales (caudal_actual), los trazos de los ríos del país (rio_cauce_mapa, ya en caché por la
// capa `rio`) y sus avisos (rio_cauce_senal) salen de la misma caché que usan el mapa y el panel.
// El río más cercano (`cercano`, lib/zonaAhora.js rioCercano) se elige entre los vigilados del
// departamento y los ~100 ríos con trazo de ANA; sus zonas estimadas (rio_cauce_zona_mapa) se piden
// solo para ese río. El titular interpretado de la BD (titular_zona.titular_corto, <= 110) es
// opcional y solo reemplaza el TEXTO cuando coincide en nivel con el que se calcula aquí y es
// fresco: el semáforo y la instrucción nunca dependen de él.
export function useZonaAhora({ p, rios, userPos, porGps, ciudad, depto }) {
  const [zonas, setZonas] = useState(null);
  const [caudales, setCaudales] = useState([]);
  const [cauces, setCauces] = useState(null);
  const [senalesCauces, setSenalesCauces] = useState([]);
  const [zonasCauce, setZonasCauce] = useState({}); // rio_ana -> filas normalizadas ([] si no tiene)
  const [titularBd, setTitularBd] = useState(null);
  const vivo = useRef(true);

  useEffect(() => {
    vivo.current = true;
    const cargar = () => {
      getZonasRio()
        .then((z) => vivo.current && setZonas(z ?? []))
        .catch((e) => console.error("zonas", e));
      getCaudales()
        .then((c) => vivo.current && setCaudales(c ?? []))
        .catch((e) => console.error("caudales", e));
      // los ríos del país son opcionales: sin ellos la tarjeta sigue con los vigilados
      getCaucesRios()
        .then((c) => vivo.current && setCauces(c ? aligerar(c) : [])) // las geometrías quedan en GEOMETRIAS
        .catch((e) => console.error("ríos del país", e));
      getSenalesCauces()
        .then((s) => vivo.current && setSenalesCauces(s ?? []))
        .catch((e) => console.error("avisos de los ríos del país", e));
    };
    cargar();
    const id = setInterval(cargar, CADA_MS);
    return () => {
      vivo.current = false;
      clearInterval(id);
    };
  }, []);

  useEffect(() => {
    let activo = true;
    const cargar = () =>
      getTitular(depto)
        .then((t) => activo && setTitularBd(t))
        .catch(() => activo && setTitularBd(null));
    cargar();
    const id = setInterval(cargar, CADA_MS);
    return () => {
      activo = false;
      clearInterval(id);
    };
  }, [depto]);

  // desde dónde se mide: tu GPS o el centro de la ciudad elegida
  const origen = useMemo(
    () => (userPos ? [userPos[0], userPos[1]] : ciudad ? [ciudad.lat, ciudad.lon] : null),
    [userPos, ciudad]
  );

  // los ríos del país con su estado de hoy (la simulación de desarrollo, igual que las capas)
  const trazados = useMemo(
    () => riosTrazados(cauces, caudales, senalesCauces, (rios ?? []).map((r) => r.rio), { simular: (e) => simularCauce(e) }),
    [cauces, caudales, senalesCauces, rios]
  );
  // el río que manda en el titular (vigilado) y el más cercano para los chips; se calculan solo
  // cuando cambian el origen o los ríos (recorrer los vértices de 100 cauces en cada render sería
  // tirar trabajo)
  const vigilado = useMemo(() => rioPrincipal(rios, origen), [rios, origen]);
  const cercano = useMemo(() => rioCercano(rios, trazados, origen), [rios, trazados, origen]);
  const principal = useMemo(
    () => vigilado ?? (cercano?.trazado && cercano.metros <= LEJOS_M ? cercano : null),
    [vigilado, cercano]
  );

  // zonas estimadas del río del país más cercano (una consulta por río, en caché 60 min)
  const idCercano = cercano?.trazado ? cercano.rio.id : null;
  useEffect(() => {
    if (!idCercano || zonasCauce[idCercano]) return;
    let activo = true;
    getCaucesZonas([idCercano])
      .then((z) => activo && setZonasCauce((prev) => ({ ...prev, [idCercano]: zonasDeCauce(z ?? []) })))
      .catch((e) => {
        console.error("zonas del río", e);
        if (activo) setZonasCauce((prev) => ({ ...prev, [idCercano]: [] }));
      });
    return () => {
      activo = false;
    };
  }, [idCercano, zonasCauce]);

  const zonasCercano = cercano?.trazado ? zonasCauce[idCercano] ?? null : zonas;
  const d = useMemo(() => (cercano ? distancias(origen, cercano.rio, zonasCercano ?? []) : null), [origen, cercano, zonasCercano]);

  return useMemo(() => {
    const nivel = nivelMaximo(p?.nivelLocal, rios);
    const base = titularCorto(p, rios, depto, { origen });
    let titular = base;
    // texto de la BD solo si está fresco, es del mismo nivel y no es una alerta o emergencia
    // (ahí manda la frase determinista con la fuente y la hora); titular_corto (<= 110 por la BD)
    // o, mientras la fila no lo tenga, el titular si cabe en dos líneas
    const bdFresco =
      Boolean(titularBd?.titular) &&
      Date.now() - Date.parse(titularBd.revisado_en ?? titularBd.generado_en ?? 0) < TITULAR_FRESCO_MS;
    const textoBd = titularBd?.titular_corto || (titularBd?.titular?.length <= TITULAR_MAX ? titularBd.titular : null);
    if (
      bdFresco &&
      textoBd &&
      textoBd.length <= TITULAR_MAX &&
      titularBd.nivel === base.nivel &&
      !esFuerte(base.nivel) &&
      base.origen !== "sin_datos" &&
      base.origen !== "error"
    ) {
      titular = { ...base, texto: textoBd, interpretado: titularBd.origen };
    }
    const zonasCargadas = zonasCercano != null;
    const chips = cercano ? chipsDistancia(d, cercano.rio, cercano.estado?.nivel) : [];
    const sinZonas = cercano ? chipSinZonas(d, cercano.rio, zonasCargadas) : null;
    if (sinZonas) chips.push(sinZonas);
    // hay un río del que hablar: un vigilado del departamento o un río con trazo a menos de 30 km
    const hayRios = (rios ?? []).length > 0 || Boolean(cercano?.trazado && cercano.metros <= LEJOS_M);
    const hayTrazadosDepto = trazados.some((t) => rioEnDepto(t.rio, depto));
    const boton = botonPrincipal(nivel, { hayRios, hayAcudir: Boolean(origen) });
    const fuentes = lineaFuentes({
      porGps,
      ciudad: ciudad?.name,
      actualizado: p?.actualizado,
      desactualizado: p?.desactualizado,
      lluviaActualizada: p?.lluviaActualizada,
      lluviaDesactualizada: p?.lluviaDesactualizada,
    });
    // la fila de ANA del río principal (con la simulación de desarrollo, igual que las capas)
    let caudal = null;
    if (principal?.rio) {
      if (principal.trazado) caudal = principal.simulado ? principal.est?.peor ?? null : caudalDelRio(principal.rio, caudales);
      else {
        const c0 = caudalDelRio(principal.rio, caudales);
        caudal = conSimulacion({ rio: principal.rio, caudal: c0, senal: null }).caudal ?? c0;
      }
    }
    return {
      origen,
      porGps,
      nivel,
      titular,
      instruccion: titular.instruccion,
      chips,
      boton,
      fuentes,
      principal,
      cercano,
      // lo que recibe "Ver el río en el mapa" (App.verRio): para un río del país, tú y el cauce
      verRio: cercano ? rioParaVer(cercano.rio, origen) : null,
      d,
      caudal,
      zonas,
      zonasCargadas,
      // el resumen de la BD (fresco) para la altura completa, aunque no se use arriba
      resumenBd: bdFresco ? titularBd : null,
      hayRios,
      hayTrazadosDepto,
      fuerte: esFuerte(nivel),
    };
  }, [p, rios, trazados, origen, porGps, ciudad, depto, zonas, zonasCercano, caudales, titularBd, principal, cercano, d]);
}
