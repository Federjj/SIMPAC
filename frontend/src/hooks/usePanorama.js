import { useCallback, useEffect, useRef, useState } from "react";
import {
  getAlertasVigentes,
  getCaudales,
  getComunicadoENFEN,
  getIndices,
  getLatido,
  getLluvia24h,
  getLluviaAhora,
} from "@/lib/queries";
import { frasesEstado } from "@/lib/nivel";
import { referenciaLluvia, resumenLluvia, textoEnfen, textoMar, textoPacifico } from "@/lib/lenguaje";
import { fechaPeru, horasDesde } from "@/lib/tiempo";

const CADA_MS = 10 * 60_000; // la ingesta es horaria: 10 min sobra
const MIN_ENTRE_CARGAS_MS = 60_000;
const DESACTUALIZADO_H = 3; // la ingesta corre cada hora: 3 h sin correr es que algo se cayó
const LLUVIA_DESACTUALIZADA_H = 1.5; // lluvia_nacional corre cada 30 min: tres vueltas sin correr

// Qué no respondió en la última corrida de la ingesta y de lluvia_nacional (latido.resumen.fallas).
function avisosDeFallas(fallas = [], fallasLluvia = []) {
  const avisos = [];
  if (fallas.includes(`ana:${fechaPeru()}`)) avisos.push("ANA no respondió en la última actualización: los ríos pueden estar atrasados.");
  const series = fallas.find((f) => f.startsWith("senamhi:series:"));
  if (series) {
    const [malas, total] = series.split(":").pop().split("/").map(Number);
    if (malas === total) avisos.push("SENAMHI no respondió en la última actualización: la lluvia de las últimas 24 h puede estar atrasada.");
  }
  if (fallasLluvia.includes("umbrales")) {
    avisos.push("SENAMHI no respondió en la última consulta de lluvia por estación: la lluvia de la última hora puede estar atrasada.");
  }
  return avisos;
}

// Panorama para la zona del usuario (`depto`) y el país: alertas, El Niño en palabras y
// lluvia (la de la última hora con su referencia, y la de las últimas 24 h). Se recarga cada
// 10 min y al volver a la pestaña. Mientras no hay datos (o si falla la consulta) no se
// afirma nada: el estado queda "Sin datos".
export function usePanorama(depto) {
  const [datos, setDatos] = useState({
    indices: [], alertas: null, enfen: null, latido: null, caudales: [], lluvia: { depto: null, filas: [] }, lluviaAhora: null,
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
      lluviaAhora: getLluviaAhora(), // la misma caché de 5 min que la capa del mapa
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
  const nacional = latido?.find((l) => l.servicio === "lluvia_nacional") ?? null;
  // solo el worker nuevo escribe 'alertas', y con número solo si en su última corrida evaluó
  // las estaciones: recién entonces cada lectura de lluvia_senamhi_actual pasó por la regla y
  // se puede decir "ninguna pasa". Con null (migración pendiente, capa caída, ninguna
  // evaluable) no se afirma: puede que esas lecturas nunca hayan pasado por la regla.
  const lluviaRevisada =
    nacional?.resumen?.alertas != null && Array.isArray(datos.lluviaAhora) && !errores.lluviaAhora;

  // Qué vigila SIMPAC en la zona: ríos con nivel de alerta de ANA y estaciones de SENAMHI
  // con lluvia de la última hora y referencia (las que la regla puede revisar). `lluviaFuera`:
  // las mismas estaciones en el resto del país (en todo el país sin departamento).
  const cobertura = {
    rios: caudales.filter((c) => c.departamento === depto && c.umbral_alerta != null && c.valor != null).length,
    lluvia: lluviaRevisada
      ? datos.lluviaAhora.filter((e) => e.departamento === depto && referenciaLluvia(e).evaluable).length
      : 0,
    lluviaFuera: lluviaRevisada
      ? datos.lluviaAhora.filter((e) => (!depto || e.departamento !== depto) && referenciaLluvia(e).evaluable).length
      : 0,
    lluviaRevisada,
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
    avisos: avisosDeFallas(ingesta?.resumen?.fallas, nacional?.resumen?.fallas),
    actualizado,
    sinConexion: Boolean(errores.latido && errores.alertas),
    desactualizado: actualizado != null && horasDesde(actualizado) >= DESACTUALIZADO_H,
    // la lluvia de la última hora tiene su propia tarea (y su propio reloj)
    lluviaActualizada: nacional?.ts ?? null,
    lluviaDesactualizada: nacional?.ts != null && (Date.now() - Date.parse(nacional.ts)) / 3_600_000 >= LLUVIA_DESACTUALIZADA_H,
    refresh: cargar,
  };
}
