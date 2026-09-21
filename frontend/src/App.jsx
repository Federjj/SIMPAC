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
import { getIndices, getCaudales, getMapaAnomalias } from "./lib/queries";
import { NIVEL, nivelDeCaudales } from "./lib/nivel";

export default function App() {
  const [visible, setVisible] = useState({ est: false, rio: true, inc: true, zona: true, anom: false });
  const [showLayers, setShowLayers] = useState(false);
  const [city, setCity] = useState(DEFAULT_CITY.name);
  const [focus, setFocus] = useState({ lat: DEFAULT_CITY.lat, lon: DEFAULT_CITY.lon, zoom: 14 });
  const [userPos, setUserPos] = useState(null);
  const mapRef = useRef(null);

  // Datos reales del backend (Supabase)
  const [oni, setOni] = useState(null);
  const [icen, setIcen] = useState(null);
  const [alertCount, setAlertCount] = useState(0);
  const [nivel, setNivel] = useState("normal");
  const [anomGeo, setAnomGeo] = useState(null);

  useEffect(() => {
    getIndices()
      .then((rows) => {
        setOni(rows.find((r) => r.fuente === "ONI") || null);
        setIcen(rows.find((r) => r.fuente === "ICEN") || null);
      })
      .catch((e) => console.error("indices", e));
    getCaudales()
      .then((rows) => {
        const activos = rows.filter((c) => c.estado === "alerta" || c.estado === "emergencia");
        setAlertCount(activos.length);
        setNivel(nivelDeCaudales(rows));
      })
      .catch((e) => console.error("caudales", e));
    getMapaAnomalias()
      .then((m) => setAnomGeo(m?.geojson || null))
      .catch((e) => console.error("anomalias", e));
  }, []);

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

  const nv = NIVEL[nivel];
  const titular =
    nivel === "emergencia"
      ? `${alertCount} río(s) en emergencia por caudal`
      : nivel === "alerta"
        ? `${alertCount} río(s) en alerta por caudal`
        : "Sin alertas de caudal activas";

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar active="mapa" nivel={nivel} alertCount={alertCount} oni={oni} icen={icen} />

      <main className="relative flex-1 h-screen">
        <MapView
          visible={visible}
          focus={focus}
          userPos={userPos}
          anomGeo={anomGeo}
          onReady={(m) => (mapRef.current = m)}
        />

        {/* Chip de marca + estado */}
        <div className="absolute left-4 top-4 z-[600] flex items-center gap-2 rounded-full border border-border bg-card/85 px-3.5 py-1.5 text-sm font-semibold shadow-lg backdrop-blur">
          <span className="text-primary">SIMPAC</span>
          <span className={`h-1.5 w-1.5 rounded-full ${nv.dot}`} />
          <span className={nv.text}>{nv.label}</span>
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

        <StatusPanel
          titular={titular}
          nivel={nivel}
          alertCount={alertCount}
          oni={oni}
          icen={icen}
        />
      </main>
    </div>
  );
}
