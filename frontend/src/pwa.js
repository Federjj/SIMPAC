// Registro del service worker (public/sw.js): guarda la cáscara de la app (JS, CSS, index.html) para
// abrir rápido y sin red; nunca datos. Solo en la build de producción (en desarrollo Vite sirve los
// módulos sueltos y un SW los dejaría viejos) y nunca dentro de la app de Capacitor (ahí los
// archivos ya son locales y el WebView de Android no lo necesita).
// Se llama una vez desde main.jsx: import { registrarServiceWorker } from "./pwa"; registrarServiceWorker();
export function registrarServiceWorker() {
  if (!import.meta.env.PROD) return;
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return;
  if (window.Capacitor?.isNativePlatform?.()) return;
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((e) => console.warn("service worker", e));
  });
}
