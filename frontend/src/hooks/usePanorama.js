import { useCallback, useEffect, useRef, useState } from "react";
import {
  getAlertasVigentes,
  getCaudales,
  getComunicadoENFEN,
  getIndices,
  getLatido,
  getLluvia24h,
} from "@/lib/queries";
import { frasesEstado } from "@/lib/nivel";
import { resumenLluvia, textoEnfen, textoMar, textoPacifico } from "@/lib/lenguaje";
import { fechaPeru, horasDesde } from "@/lib/tiempo";

const CADA_MS = 10 * 60_000; // la ingesta es horaria: 10 min sobra
const MIN_ENTRE_CARGAS_MS = 60_000;
const DESACTUALIZADO_H = 3; // la ingesta corre cada hora: 3 h sin correr es que algo se cayó

// Qué no respondió en la última corrida de la ingesta (latido.resumen.fallas).
function avisosDeFallas(fallas = []) {
  const avisos = [];
  if (fallas.includes(`ana:${fechaPeru()}`)) avisos.push("ANA no respondió en la última actualización: los ríos pueden estar atrasados.");
  const series = fallas.find((f) => f.startsWith("senamhi:series:"));
  if (series) {
    const [malas, total] = series.split(":").pop().split("/").map(Number);
    if (malas === total) avisos.push("SENAMHI no respondió en la última actualización: la lluvia puede estar atrasada.");
  }
  return avisos;
}

// Panorama para la zona del usuario (`depto`) y el país: alertas, El Niño en palabras y
// lluvia de las últimas 24 h. Se recarga cada 10 min y al volver a la pestaña. Mientras
// no hay datos (o si falla la consulta) no se afirma nada: el estado queda "Sin datos".
export function usePanorama(depto) {
  const [datos, setDatos] = useState({
    indices: [], alertas: null, enfen: null, latido: null, caudales: [], lluvia: { depto: null, filas: [] },
  });
  const [errores, setErrores] = useState({});
  const ultima = useRef(0);
  const deptoActual = useRef(depto);
  deptoActual.current = depto;

  const cargar = useCallback(async () => {
    ultima.current = Date.now();
    const pedidos = {
      indices: getIndices(),
      alertas: getAlertasVigentes(),
      enfen: getComunicadoENFEN(),
      latido: getLatido(),
      caudales: getCaudales(),
      lluvia: depto ? getLluvia24h(depto).then((filas) => ({ depto, filas })) : Promise.resolve({ depto, filas: [] }),
    };
    const claves = Object.keys(pedidos);
    const res = await Promise.allSettled(Object.values(pedidos));
    const nuevosErrores = {};
    setDatos((prev) => {
      const nuevo = { ...prev };
      res.forEach((r, i) => {
        const k = claves[i];
        if (r.status === "rejected") {
          console.error(k, r.reason);
          nuevosErrores[k] = true;
          return;
        }
        // una respuesta de un departamento anterior (cambio de ciudad en vuelo) se descarta
        if (k === "lluvia" && r.value.depto !== deptoActual.current) return;
        nuevo[k] = r.value;
      });
      return nuevo;
    });
    setErrores(nuevosErrores);
  }, [depto]);

  useEffect(() => {
    cargar();
    const id = setInterval(cargar, CADA_MS);
    const alVolver = () => {
      if (document.visibilityState === "visible" && Date.now() - ultima.current > MIN_ENTRE_CARGAS_MS) cargar();
    };
    document.addEventListener("visibilitychange", alVolver);
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", alVolver);
    };
  }, [cargar]);

  const { indices, alertas, enfen, latido, caudales } = datos;
  // la lluvia solo cuenta si es del departamento que se está mirando
  const lluvia = datos.lluvia.depto === depto ? datos.lluvia.filas : [];
  const indice = (f) => indices.find((r) => r.fuente === f) ?? null;
  const ingesta = latido?.find((l) => l.servicio === "ingesta") ?? null;
  const actualizado = ingesta?.ts ?? null;

  // Qué vigila SIMPAC en la zona: ríos con nivel de alerta de ANA y estaciones de lluvia.
  const cobertura = {
    rios: caudales.filter((c) => c.departamento === depto && c.umbral_alerta != null && c.valor != null).length,
    lluvia: new Set(lluvia.filter((f) => f.precip_mm != null).map((f) => f.cod)).size,
  };

  return {
    ...frasesEstado(alertas, depto, cobertura, Boolean(errores.alertas)),
    alertas,
    enfen: textoEnfen(enfen),
    // valores crudos para el gráfico de El Niño
    icen: indice("ICEN"),
    icenTmp: indice("ICEN_TMP"),
    mar: textoMar(indice("ICEN"), indice("ICEN_TMP")),
    pacifico: textoPacifico(indice("RONI")),
    lluvia: resumenLluvia(lluvia, depto),
    avisos: avisosDeFallas(ingesta?.resumen?.fallas),
    actualizado,
    sinConexion: Boolean(errores.latido && errores.alertas),
    desactualizado: actualizado != null && horasDesde(actualizado) >= DESACTUALIZADO_H,
    refresh: cargar,
  };
}
