import { useEffect } from "react";

// Publica el alto de la hoja inferior en <html style="--hoja-alto"> para que, en el celular, los
// controles de Leaflet (zoom y atribución, abajo a la derecha) suban y no queden tapados
// (index.css: .leaflet-bottom). Se mide con ResizeObserver: una vez por cambio de altura, no por
// cuadro. Desde lg la hoja es una tarjeta a la izquierda y la variable no se usa.
export function useAltoHoja(ref) {
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return undefined;
    const raiz = document.documentElement;
    const medir = () => raiz.style.setProperty("--hoja-alto", `${Math.round(el.getBoundingClientRect().height) + 8}px`);
    medir();
    const ro = new ResizeObserver(medir);
    ro.observe(el);
    return () => {
      ro.disconnect();
      raiz.style.removeProperty("--hoja-alto");
    };
  }, [ref]);
}
