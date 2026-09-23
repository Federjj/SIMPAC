import { useEffect, useMemo, useState } from "react";
import { getPronosticoVigente } from "@/lib/queries";
import { fechaPeru } from "@/lib/tiempo";
import { pronosticoLocal } from "@/lib/pronostico";

const CADA_MS = 30 * 60_000;

// Pronóstico de SENAMHI de tu localidad para la franja de 3 días del panel: la de la ciudad
// elegida o, con GPS, la localidad con pronóstico más cercana (hasta 10 km "ok", hasta 30 km
// "cercana", más lejos "lejos"). Se recarga cada 30 min. La lógica vive en lib/pronostico.js.
// Devuelve {estado, localidad, dias, emision, atrasado}; estado: cargando | ok | cercana | lejos |
// sin_datos | error | sin_servicio (la vista aún no existe: la franja no se muestra).
export function usePronosticoLocal({ ciudad, porGps, userPos }) {
  const [filas, setFilas] = useState(undefined);
  const [error, setError] = useState(null);
  const [hoy, setHoy] = useState(fechaPeru);

  useEffect(() => {
    let vivo = true;
    const cargar = () =>
      getPronosticoVigente()
        .then((f) => {
          if (!vivo) return;
          setFilas(f);
          setError(null);
          setHoy(fechaPeru()); // pasada la medianoche, "Hoy" pasa al día siguiente
        })
        .catch((e) => vivo && setError(e));
    cargar();
    const t = setInterval(cargar, CADA_MS);
    return () => {
      vivo = false;
      clearInterval(t);
    };
  }, []);

  // una recarga fallida no borra lo que ya se tenía
  return useMemo(
    () => pronosticoLocal({ filas, error: filas === undefined ? error : null, ciudad, porGps, userPos, hoy }),
    [filas, error, ciudad, porGps, userPos, hoy]
  );
}
