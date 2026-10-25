import { useCallback, useState } from "react";

// Ubicación real del dispositivo (GPS) con navigator.geolocation. Es la única posición válida
// para reportar: no hay pin manual, así nadie reporta desde donde no está.
// status: idle | pending | granted | denied | unavailable
//
// Dentro de la app Android (Kotlin, appmobile/android) la misma API funciona: el WebView del Mapa
// concede la geolocalización del sistema al origen de la web (ui/mapa/MapaScreen.kt). La rama con
// el plugin de Capacitor se retiró el 2026-10-24 junto con esa app.

const OPCIONES = { enableHighAccuracy: true, timeout: 8000 };

// [lat, lon] con la API del navegador; lanza { code: "denied" | "unavailable" } si no se pudo.
function ubicarWeb() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject({ code: "unavailable" });
    navigator.geolocation.getCurrentPosition(
      (p) => resolve([p.coords.latitude, p.coords.longitude]),
      (err) => reject({ code: err.code === err.PERMISSION_DENIED ? "denied" : "unavailable" }),
      OPCIONES
    );
  });
}

export function useGeolocation() {
  const [pos, setPos] = useState(null);
  const [status, setStatus] = useState("idle");

  // Devuelve una promesa con [lat, lon], o null si no se pudo.
  const locate = useCallback(async () => {
    setStatus("pending");
    try {
      const lugar = await ubicarWeb();
      setPos(lugar);
      setStatus("granted");
      return lugar;
    } catch (err) {
      setStatus(err?.code === "denied" ? "denied" : "unavailable");
      return null;
    }
  }, []);

  return { pos, status, locate };
}
