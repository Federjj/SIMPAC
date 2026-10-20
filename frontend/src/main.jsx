import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "leaflet/dist/leaflet.css";
import "./index.css";
import App from "./App.jsx";
import { montarDefsIconos } from "./map/iconos";
import { registrarServiceWorker } from "./pwa";

// degradados de los glifos del tiempo (una sola vez, antes de dibujar cualquiera)
montarDefsIconos();
// service worker (public/sw.js): cáscara de la app sin red; solo en producción y fuera de Capacitor
registrarServiceWorker();

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
