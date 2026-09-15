import { useEffect, useRef, useState } from "react";
import Sidebar from "./components/Sidebar.jsx";
import MapView from "./components/MapView.jsx";
import LayersPanel from "./components/LayersPanel.jsx";
import StatusPanel from "./components/StatusPanel.jsx";
import CitySelector from "./components/CitySelector.jsx";
import { CITIES, DEFAULT_CITY, nearestCity } from "./data/cities";
import { IcLayers, IcLocate, IcPlus } from "./icons.jsx";

const METRICS = { lluvia: "2.4", rio: "48.2", temp: "14°C" };

export default function App() {
  const [visible, setVisible] = useState({ est: true, rio: true, inc: true, usr: false, zona: true });
  const [showLayers, setShowLayers] = useState(false);
  const [city, setCity] = useState(DEFAULT_CITY.name);
  const [focus, setFocus] = useState({ lat: DEFAULT_CITY.lat, lon: DEFAULT_CITY.lon, zoom: 14 });
  const [userPos, setUserPos] = useState(null);
  const mapRef = useRef(null);

  const toggle = (id) => setVisible((v) => ({ ...v, [id]: !v[id] }));

  const pickCity = (name) => {
    const c = CITIES.find((x) => x.name === name) || DEFAULT_CITY;
    setCity(c.name);
    setFocus({ lat: c.lat, lon: c.lon, zoom: 14 });
  };

  // Detecta la ubicación real (con permiso); si falla, se queda en Cajamarca.
  const geolocate = () => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude: lat, longitude: lon } = pos.coords;
        setUserPos([lat, lon]);
        setFocus({ lat, lon, zoom: 15 });
        setCity(nearestCity(lat, lon).name);
      },
      () => { /* permiso denegado / no disponible: se mantiene Cajamarca */ },
      { enableHighAccuracy: true, timeout: 8000 }
    );
  };

  useEffect(() => { geolocate(); }, []);

  return (
    <div className="app">
      <Sidebar active="mapa" metrics={METRICS} />

      <main className="main">
        <MapView visible={visible} focus={focus} userPos={userPos} onReady={(m) => (mapRef.current = m)} />

        <div className="chip"><b>SIMPAC</b><span className="d" /><span className="st">Alerta</span></div>
        <CitySelector value={city} onChange={pickCity} />

        <div className="tools">
          <button className="tool" title="Capas" onClick={() => setShowLayers((s) => !s)}><IcLayers /></button>
          <button className="tool" title="Mi ubicación" onClick={geolocate}><IcLocate /></button>
        </div>

        {showLayers && <LayersPanel visible={visible} onToggle={toggle} />}

        <button className="report"><IcPlus size={18} /> Reportar</button>

        <StatusPanel titular="Lluvias intensas. Tome precauciones" metrics={METRICS} />
      </main>
    </div>
  );
}
