import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { estadoPermiso, revisarEntorno, ubicar } from "@/lib/geolocalizacion";

// Ubicación real del dispositivo con navigator.geolocation. Es la única posición válida para
// reportar: no hay pin manual, así nadie reporta desde donde no está.
//
// La estrategia (lib/geolocalizacion.js ubicar) va en dos tiempos: una lectura rápida de baja
// precisión (red, hasta 6 s) para tener algo ya y un watchPosition de alta precisión hasta 22 s
// que se queda con la mejor lectura y para al bajar de 30 m. Mientras afina, `pos` se va
// reemplazando por la lectura mejor (solo si mejora) y `afinando` es true.
//
// Devuelve:
//   pos        [lat, lon] de la mejor lectura, o null (quien ya consumía [lat, lon] no cambia)
//   precision  metros de la mejor lectura (accuracy del navegador), o null si no se informó
//   lectura    { lat, lon, precisionM, hora } completa
//   status     idle | pending | granted | denied | unavailable | timeout | insecure
//              (denied: permiso negado; unavailable: sin señal o sin geolocalización; timeout: el
//              GPS no respondió a tiempo; insecure: http sin localhost). Textos en
//              lib/geolocalizacion.js TEXTO_ESTADO.
//   afinando   true mientras el GPS sigue buscando una lectura mejor
//   locate     () -> Promise<[lat, lon] | null>: pide la ubicación (rápida + GPS)
//   afinar     () -> Promise<[lat, lon] | null>: solo el GPS, partiendo de la lectura que hay
//              ("Mejorar precisión"); el status no cambia
//   cancelar   () corta la búsqueda en curso sin esperar su resultado (la persona eligió su ciudad
//              mientras el GPS buscaba): la promesa de locate o afinar resuelve null y, si estaba
//              buscando, el status vuelve a idle
//
// Si la Permissions API dice que el permiso está negado no se llama al navegador (status denied
// de una); si está concedido, la rápida y el GPS arrancan juntos; si está por pedir, el GPS
// espera a la rápida para que el navegador muestre un solo pedido de permiso.
//
// Dentro de la app Android (Kotlin, appmobile/android) la misma API funciona: el WebView del Mapa
// concede la geolocalización del sistema al origen de la web (ui/mapa/MapaScreen.kt). La rama con
// el plugin de Capacitor se retiró el 2026-10-24 junto con esa app.

export function useGeolocation() {
  const [lectura, setLectura] = useState(null);
  const [status, setStatus] = useState("idle");
  const [afinando, setAfinando] = useState(false);
  const lecturaRef = useRef(null);
  const sesion = useRef(null); // { id, cancelar } de la búsqueda en curso
  const contador = useRef(0);

  // al desmontar se corta lo que estuviera buscando
  useEffect(() => () => sesion.current?.cancelar?.(), []);

  const actualizar = useCallback((l) => {
    lecturaRef.current = l;
    setLectura(l);
  }, []);

  const correr = useCallback(
    async ({ rapida }) => {
      sesion.current?.cancelar?.();
      const id = ++contador.current;
      sesion.current = { id, cancelar: null };
      const vigente = () => sesion.current?.id === id;

      const problema = revisarEntorno(globalThis);
      if (problema) {
        if (rapida) setStatus(problema);
        setAfinando(false);
        return null;
      }
      if (rapida) setStatus("pending");
      setAfinando(true);

      const permiso = await estadoPermiso(globalThis.navigator);
      if (!vigente()) return null;

      const s = ubicar(globalThis.navigator.geolocation, {
        permiso,
        rapida,
        desde: rapida ? null : lecturaRef.current,
        onMejora: (l) => vigente() && actualizar(l),
        onFin: () => vigente() && setAfinando(false),
      });
      if (vigente()) sesion.current.cancelar = s.cancelar;
      try {
        const l = await s.primera;
        if (!vigente()) return null;
        actualizar(l);
        setStatus("granted");
        return [l.lat, l.lon];
      } catch (err) {
        if (!vigente() || err?.code === "cancelado") return null;
        if (rapida) setStatus(err?.code ?? "unavailable");
        setAfinando(false);
        // al afinar sin éxito se conserva la lectura que había
        const previa = rapida ? null : lecturaRef.current;
        return previa ? [previa.lat, previa.lon] : null;
      }
    },
    [actualizar]
  );

  const locate = useCallback(() => correr({ rapida: true }), [correr]);
  const afinar = useCallback(() => correr({ rapida: false }), [correr]);
  // Cancelar desde fuera: se suelta la sesión primero (vigente() pasa a falso, así lo que siga de
  // esa búsqueda, incluso si todavía esperaba a la Permissions API, ya no se aplica) y se corta.
  const cancelar = useCallback(() => {
    const s = sesion.current;
    if (!s) return;
    sesion.current = null;
    s.cancelar?.();
    setStatus((actual) => (actual === "pending" ? "idle" : actual));
    setAfinando(false);
  }, []);

  const pos = useMemo(() => (lectura ? [lectura.lat, lectura.lon] : null), [lectura]);
  const precision = lectura?.precisionM ?? null;

  return { pos, precision, lectura, status, afinando, locate, afinar, cancelar };
}
