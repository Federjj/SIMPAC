import { useCallback, useState } from "react";

// Ubicación real del dispositivo (GPS). Es la única posición válida para reportar:
// no hay pin manual, así nadie reporta desde donde no está.
// status: idle | pending | granted | denied | unavailable
export function useGeolocation() {
  const [pos, setPos] = useState(null);
  const [status, setStatus] = useState("idle");

  // Devuelve una promesa con [lat, lon], o null si no se pudo.
  const locate = useCallback(
    () =>
      new Promise((resolve) => {
        if (!navigator.geolocation) {
          setStatus("unavailable");
          return resolve(null);
        }
        setStatus("pending");
        navigator.geolocation.getCurrentPosition(
          (p) => {
            const lugar = [p.coords.latitude, p.coords.longitude];
            setPos(lugar);
            setStatus("granted");
            resolve(lugar);
          },
          (err) => {
            setStatus(err.code === err.PERMISSION_DENIED ? "denied" : "unavailable");
            resolve(null);
          },
          { enableHighAccuracy: true, timeout: 8000 }
        );
      }),
    []
  );

  return { pos, status, locate };
}
