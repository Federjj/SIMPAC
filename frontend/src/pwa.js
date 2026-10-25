// Registro del service worker (public/sw.js): guarda la cáscara de la app (JS, CSS, index.html) para
// abrir rápido y sin red; nunca datos. Solo en la build de producción (en desarrollo Vite sirve los
// módulos sueltos y un SW los dejaría viejos). Dentro de la app Android (Kotlin) el WebView carga esta
// misma web por red, así que el service worker le sirve igual.
// Se llama una vez desde main.jsx: import { registrarServiceWorker } from "./pwa"; registrarServiceWorker();
export function registrarServiceWorker() {
  if (!import.meta.env.PROD) return;
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return;
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((e) => console.warn("service worker", e));
  });
}
