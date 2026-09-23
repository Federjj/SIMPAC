import React from "react";
import { createRoot } from "react-dom/client";
import "leaflet/dist/leaflet.css";
import "./index.css";
import App from "./App.jsx";
import { montarDefsIconos } from "./map/iconos";

// degradados de los glifos del tiempo (una sola vez, antes de dibujar cualquiera)
montarDefsIconos();

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
