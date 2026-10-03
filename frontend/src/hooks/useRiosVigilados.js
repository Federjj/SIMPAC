import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getCaudales, getRiosVigilados, getSenalesRio } from "@/lib/queries";
import { caudalDelRio, estadoZona } from "@/lib/zonaRio";
import { conSimulacion } from "@/lib/simulacion";

const CADA_MS = 5 * 60_000; // las señales (avisos y lluvia) cambian más seguido que los ríos
const MIN_ENTRE_CARGAS_MS = 60_000;

// Ríos vigilados del departamento `depto` con el nivel de hoy de su zona (lib/zonaRio.js), para el
// panel de estado: [{ rio, estado }]. Se recarga cada 5 min y al volver a la pestaña (las consultas
// comparten la caché con las capas del mapa). Sin las vistas de los ríos vigilados (migración
// pendiente) o si fallan, devuelve [] y el panel no dice nada de ellos.
export function useRiosVigilados(depto) {
  const [datos, setDatos] = useState({ rios: null, senales: null, caudales: [] });
  const ultima = useRef(0);

  const cargar = useCallback(async () => {
    ultima.current = Date.now();
    const [rios, senales, caudales] = await Promise.allSettled([getRiosVigilados(), getSenalesRio(), getCaudales()]);
    for (const r of [rios, senales, caudales]) if (r.status === "rejected") console.error("ríos vigilados", r.reason);
    setDatos((prev) => ({
      rios: rios.status === "fulfilled" ? rios.value : prev.rios,
      senales: senales.status === "fulfilled" ? senales.value : prev.senales,
      caudales: caudales.status === "fulfilled" ? caudales.value : prev.caudales,
    }));
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

  return useMemo(() => {
    const { rios, senales, caudales } = datos;
    if (!rios) return [];
    return rios
      .filter((r) => r.departamento === depto)
      .map((r) => {
        // simulación (solo en desarrollo, ?simular=...), la misma que ven las capas del mapa
        const sim = conSimulacion({ rio: r, caudal: caudalDelRio(r, caudales), senal: senales?.find((s) => s.rio === r.id) ?? null });
        return { rio: sim.rio, estado: estadoZona({ caudal: sim.caudal, senal: sim.senal }) };
      });
  }, [datos, depto]);
}
