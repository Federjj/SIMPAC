import { useCallback, useState } from "react";

// Ubicación real del dispositivo (GPS). Es la única posición válida para reportar:
// no hay pin manual, así nadie reporta desde donde no está.
// status: idle | pending | granted | denied | unavailable
//
// En la web usa navigator.geolocation. Dentro de la app Android (Capacitor) usa el plugin
// @capacitor/geolocation, que pide el permiso del sistema y lee el GPS nativo; el plugin se
// importa solo en ese caso (import dinámico) para que el bundle web no lo cargue.

const OPCIONES = { enableHighAccuracy: true, timeout: 8000 };

function esAppNativa() {
  return typeof window !== "undefined" && window.Capacitor?.isNativePlatform?.() === true;
}

// [lat, lon] con el plugin nativo; lanza { code: "denied" | "unavailable" } si no se pudo.
async function ubicarNativo() {
  const { Geolocation } = await import("@capacitor/geolocation");
  let permiso = await Geolocation.checkPermissions();
  if (permiso.location !== "granted" && permiso.coarseLocation !== "granted") {
    permiso = await Geolocation.requestPermissions({ permissions: ["location"] });
  }
  if (permiso.location !== "granted" && permiso.coarseLocation !== "granted") {
    throw { code: "denied" };
  }
  try {
    const p = await Geolocation.getCurrentPosition(OPCIONES);
    return [p.coords.latitude, p.coords.longitude];
  } catch {
    throw { code: "unavailable" };
  }
}

// [lat, lon] con la API del navegador; lanza { code } igual que arriba.
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
      const lugar = esAppNativa() ? await ubicarNativo() : await ubicarWeb();
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
