import { useEffect, useRef, useState } from "react";
import { Layers, LocateFixed, Plus } from "lucide-react";
import Sidebar from "./components/Sidebar.jsx";
import MapView from "./components/MapView.jsx";
import LayersPanel from "./components/LayersPanel.jsx";
import StatusPanel from "./components/StatusPanel.jsx";
import CitySelector from "./components/CitySelector.jsx";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { CITIES, DEFAULT_CITY, nearestCity } from "./data/cities";

const METRICS = { lluvia: "2.4", rio: "48.2", temp: "14°C" };

export default function App() {
  const [visible, setVisible] = useState({ est: false, rio: true, inc: true, zona: true });
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

  // Detecta la ubicacion real (con permiso); si falla, se queda en Cajamarca.
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
    <div className="flex h-screen overflow-hidden">
      <Sidebar active="mapa" metrics={METRICS} />

      <main className="relative flex-1 h-screen">
        <MapView visible={visible} focus={focus} userPos={userPos} onReady={(m) => (mapRef.current = m)} />

        {/* Chip de marca + estado */}
        <div className="absolute left-4 top-4 z-[600] flex items-center gap-2 rounded-full border border-border bg-card/85 px-3.5 py-1.5 text-sm font-semibold shadow-lg backdrop-blur">
          <span className="text-primary">SIMPAC</span>
          <span className="h-1.5 w-1.5 rounded-full bg-nivel-alerta" />
          <span className="text-nivel-alerta">Alerta</span>
        </div>

        {/* Selector de ciudad */}
        <div className="absolute left-4 top-[60px] z-[600]">
          <CitySelector value={city} onChange={pickCity} />
        </div>

        {/* Herramientas */}
        <TooltipProvider delayDuration={200}>
          <div className="absolute right-4 top-4 z-[600] flex flex-col gap-2">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="secondary"
                  size="icon"
                  className="rounded-xl border border-border bg-card/90 backdrop-blur"
                  onClick={() => setShowLayers((s) => !s)}
                >
                  <Layers className="h-[18px] w-[18px]" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="left">Capas</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="secondary"
                  size="icon"
                  className="rounded-xl border border-border bg-card/90 backdrop-blur"
                  onClick={geolocate}
                >
                  <LocateFixed className="h-[18px] w-[18px]" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="left">Mi ubicación</TooltipContent>
            </Tooltip>
          </div>
        </TooltipProvider>

        {showLayers && <LayersPanel visible={visible} onToggle={toggle} />}

        {/* Boton reportar flotante (solo desktop; en movil va dentro del panel) */}
        <Button
          variant="destructive"
          className="absolute bottom-6 left-4 z-[610] hidden rounded-xl shadow-xl sm:inline-flex"
        >
          <Plus className="h-[18px] w-[18px]" />
          Reportar
        </Button>

        <StatusPanel titular="Lluvias intensas. Tome precauciones" metrics={METRICS} />
      </main>
    </div>
  );
}
