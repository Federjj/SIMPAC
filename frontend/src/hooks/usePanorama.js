import { useCallback, useEffect, useRef, useState } from "react";
import { getAlertasVigentes, getIndices } from "@/lib/queries";
import { nivelDeAlertas, titularDe } from "@/lib/nivel";
import { horasDesde } from "@/lib/tiempo";

const CADA_MS = 10 * 60_000; // la ingesta es horaria: 10 min sobra
const MIN_ENTRE_CARGAS_MS = 60_000;
const DESACTUALIZADO_H = 3; // la ingesta corre cada hora: 3 h sin datos es que algo se cayó

// Panorama general: índices El Niño y alertas vigentes. Se recarga cada 10 min y
// al volver a la pestaña (si pasó al menos un minuto).
export function usePanorama() {
  const [indices, setIndices] = useState([]);
  const [alertas, setAlertas] = useState([]);
  const ultima = useRef(0);

  const cargar = useCallback(async () => {
    ultima.current = Date.now();
    const [ind, ale] = await Promise.allSettled([getIndices(), getAlertasVigentes()]);
    if (ind.status === "fulfilled") setIndices(ind.value);
    else console.error("indices", ind.reason);
    if (ale.status === "fulfilled") setAlertas(ale.value);
    else console.error("alertas", ale.reason);
  }, []);

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

  // Cada corrida de la ingesta renueva indice.ts_captura: es el latido de los datos.
  // Sin esto, si el worker se cae, las alertas viejas se verían como actuales.
  const capturas = indices.map((r) => r.ts_captura).filter(Boolean).sort();
  const actualizado = capturas.length ? capturas[capturas.length - 1] : null;

  return {
    actualizado,
    desactualizado: actualizado != null && horasDesde(actualizado) >= DESACTUALIZADO_H,
    oni: indices.find((r) => r.fuente === "ONI") ?? null,
    icen: indices.find((r) => r.fuente === "ICEN") ?? null,
    alertas,
    alertCount: alertas.length,
    nivel: nivelDeAlertas(alertas),
    titular: titularDe(alertas),
    refresh: cargar,
  };
}
