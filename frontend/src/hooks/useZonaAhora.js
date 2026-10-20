import { useEffect, useMemo, useRef, useState } from "react";
import { getCaudales, getTitular, getZonasRio } from "@/lib/queries";
import { conSimulacion } from "@/lib/simulacion";
import {
  botonPrincipal,
  caudalDelRio,
  chipsDistancia,
  distancias,
  esFuerte,
  lineaFuentes,
  nivelMaximo,
  rioPrincipal,
  titularCorto,
} from "@/lib/zonaAhora";

const CADA_MS = 5 * 60_000;
const TITULAR_FRESCO_MS = 90 * 60_000; // la tarea 'titular' corre cada 30 min: tres vueltas sin correr es viejo
const TITULAR_MAX = 110; // más largo no cabe en 2 líneas: va como resumen en la altura completa

// Lo que la tarjeta "Tu zona ahora" necesita, calculado una vez por cambio de entrada (memo):
//   p         usePanorama(depto)         rios  useRiosVigilados(depto) ([{ rio, estado }])
//   userPos   [lat, lon] del GPS o null  porGps  si la zona salió del GPS
//   ciudad    la ciudad elegida (data/cities)   depto  departamento de la zona
// Devuelve { origen, porGps, nivel, titular, chips, boton, fuentes, principal, d, caudal, zonas,
// hayRios, instruccion }. Las zonas (rio_zona_mapa) y los caudales (caudal_actual) salen de la
// misma caché que usan el mapa y el panel: no agregan pedidos. El titular interpretado de la BD
// (titular_zona) es opcional y solo reemplaza el TEXTO cuando coincide en nivel con el que se
// calcula aquí y es fresco: el semáforo y la instrucción nunca dependen de él.
export function useZonaAhora({ p, rios, userPos, porGps, ciudad, depto }) {
  const [zonas, setZonas] = useState(null);
  const [caudales, setCaudales] = useState([]);
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

  // el río que manda y las distancias se calculan solo cuando cambian el origen, los ríos o las
  // zonas (recorrer los vértices del cauce en cada render de usePanorama sería tirar trabajo)
  const principal = useMemo(() => rioPrincipal(rios, origen), [rios, origen]);
  const d = useMemo(() => (principal ? distancias(origen, principal.rio, zonas ?? []) : null), [origen, principal, zonas]);

  return useMemo(() => {
    const nivel = nivelMaximo(p?.nivelLocal, rios);
    const base = titularCorto(p, rios, depto, { origen });
    let titular = base;
    // texto de la BD solo si está fresco, es del mismo nivel y no es una alerta o emergencia
    // (ahí manda la frase determinista con la fuente y la hora)
    const bdFresco =
      Boolean(titularBd?.titular) &&
      Date.now() - Date.parse(titularBd.revisado_en ?? titularBd.generado_en ?? 0) < TITULAR_FRESCO_MS;
    if (
      bdFresco &&
      titularBd.titular.length <= TITULAR_MAX &&
      titularBd.nivel === base.nivel &&
      !esFuerte(base.nivel) &&
      base.origen !== "sin_datos" &&
      base.origen !== "error"
    ) {
      titular = { ...base, texto: titularBd.titular, interpretado: titularBd.origen };
    }
    const chips = principal ? chipsDistancia(d, principal.rio, principal.estado?.nivel) : [];
    const hayRios = (rios ?? []).length > 0;
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
      const c0 = caudalDelRio(principal.rio, caudales);
      caudal = conSimulacion({ rio: principal.rio, caudal: c0, senal: null }).caudal ?? c0;
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
      d,
      caudal,
      zonas,
      zonasCargadas: zonas != null,
      // el resumen de la BD (fresco) para la altura completa, aunque no se use arriba
      resumenBd: bdFresco ? titularBd : null,
      hayRios,
      fuerte: esFuerte(nivel),
    };
  }, [p, rios, origen, porGps, ciudad, depto, zonas, caudales, titularBd, principal, d]);
}
