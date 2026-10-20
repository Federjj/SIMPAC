import { useEffect, useRef, useState } from "react";

// Si la persona pidió menos movimiento (prefers-reduced-motion): los números aparecen en su valor
// final y las animaciones de entrada no corren (index.css pone las --dur en 0 ms; aquí se decide lo
// que va por requestAnimationFrame).
export function movimientoReducido() {
  try {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return false;
  }
}

export function useMovimientoReducido() {
  const [reducido, setReducido] = useState(movimientoReducido);
  useEffect(() => {
    let mq;
    try {
      mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    } catch {
      return undefined;
    }
    const seguir = () => setReducido(mq.matches);
    mq.addEventListener?.("change", seguir);
    return () => mq.removeEventListener?.("change", seguir);
  }, []);
  return reducido;
}

const salida = (t) => 1 - Math.pow(1 - t, 3); // ease-out cúbico

// Un número que cuenta desde el valor anterior (o desde 0 la primera vez) hasta `valor` en `dur`
// ms con requestAnimationFrame. Con prefers-reduced-motion (o valor null) devuelve el valor tal
// cual. Devuelve el número que hay que pintar en este cuadro.
export function useContador(valor, { dur = 700, desde = 0 } = {}) {
  const reducido = useMovimientoReducido();
  const [mostrado, setMostrado] = useState(() => (reducido || valor == null ? valor : desde));
  const previo = useRef(reducido || valor == null ? valor : desde);
  useEffect(() => {
    // con la pestaña oculta requestAnimationFrame no corre: el valor final va directo
    const oculta = typeof document !== "undefined" && document.visibilityState === "hidden";
    if (valor == null || reducido || dur <= 0 || oculta) {
      previo.current = valor;
      setMostrado(valor);
      return undefined;
    }
    // se parte del último número pintado (previo), no del valor pedido: en desarrollo React monta
    // los efectos dos veces y, si la limpieza diera por llegado el valor, el número quedaría en 0
    const inicio = previo.current ?? 0;
    if (inicio === valor) {
      setMostrado(valor);
      return undefined;
    }
    let id;
    let t0;
    // red de seguridad: si el navegador frena los cuadros (pestaña de fondo, ahorro de batería),
    // el valor final se pinta igual poco después del tiempo previsto
    const tope = setTimeout(() => {
      cancelAnimationFrame(id);
      previo.current = valor;
      setMostrado(valor);
    }, dur + 250);
    const paso = (ts) => {
      if (t0 == null) t0 = ts;
      const t = Math.min(1, (ts - t0) / dur);
      const v = t >= 1 ? valor : inicio + (valor - inicio) * salida(t);
      previo.current = v;
      setMostrado(v);
      if (t < 1) id = requestAnimationFrame(paso);
      else clearTimeout(tope);
    };
    id = requestAnimationFrame(paso);
    return () => {
      cancelAnimationFrame(id);
      clearTimeout(tope);
    };
  }, [valor, dur, reducido]);
  return mostrado;
}
