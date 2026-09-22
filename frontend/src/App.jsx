import { useEffect, useState } from "react";
import { Layers, LocateFixed, Plus } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import MapView from "@/components/MapView";
import LayersPanel from "@/components/LayersPanel";
import StatusPanel from "@/components/StatusPanel";
import CitySelector from "@/components/CitySelector";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { CITIES, DEFAULT_CITY, nearestCity } from "@/data/cities";
import { LAYERS } from "@/map/layers";
import { NIVEL } from "@/lib/nivel";
import { departamentoEn } from "@/lib/ubicacion";
import { usePanorama } from "@/hooks/usePanorama";
import { useGeolocation } from "@/hooks/useGeolocation";
import { useLayerVisibility } from "@/hooks/useLayerVisibility";

export default function App() {
  const { visible, toggle } = useLayerVisibility(LAYERS);
  const [showLayers, setShowLayers] = useState(false);
  const [city, setCity] = useState(DEFAULT_CITY.name);
  const [focus, setFocus] = useState({ lat: DEFAULT_CITY.lat, lon: DEFAULT_CITY.lon, zoom: 14 });
  const { pos: userPos, locate } = useGeolocation();
  // Zona del usuario: el departamento de la ciudad elegida o el de su GPS.
  const [depto, setDepto] = useState(DEFAULT_CITY.depto);
  const [porGps, setPorGps] = useState(false);
  const p = usePanorama(depto);

  const pickCity = (name) => {
    const c = CITIES.find((x) => x.name === name) || DEFAULT_CITY;
    setCity(c.name);
    setDepto(c.depto);
    setPorGps(false);
    setFocus({ lat: c.lat, lon: c.lon, zoom: 14 });
  };

  // Ubicación real (con permiso); si falla, el mapa se queda en Cajamarca.
  const geolocate = async () => {
    const lugar = await locate();
    if (!lugar) return;
    const [lat, lon] = lugar;
    setFocus({ lat, lon, zoom: 15 });
    const cercana = nearestCity(lat, lon);
    setCity(cercana.name);
    setDepto((await departamentoEn(lat, lon).catch(() => null)) ?? cercana.depto);
    setPorGps(true);
  };

  useEffect(() => {
    geolocate();
  }, []);

  const nv = NIVEL[p.nivelLocal];

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        active="mapa"
        depto={depto}
        nivel={p.nivelLocal}
        alertCount={p.cuantasAqui + p.cuantasFuera}
        enfen={p.enfen}
        mar={p.mar}
        pacifico={p.pacifico}
        actualizado={p.actualizado}
        desactualizado={p.desactualizado}
        sinConexion={p.sinConexion}
      />

      <main className="relative flex-1 h-screen">
        <MapView layers={LAYERS} visible={visible} focus={focus} userPos={userPos} />

        {/* Chip de marca + estado */}
        <div className="absolute left-4 top-4 z-[600] flex items-center gap-2 rounded-full border border-border bg-card/85 px-3.5 py-1.5 text-sm font-semibold shadow-lg backdrop-blur">
          <span className="text-primary">SIMPAC</span>
          <span className={`h-1.5 w-1.5 rounded-full ${nv.dot}`} />
          <span className={nv.text}>
            {nv.label} en {depto}
          </span>
        </div>

        {/* Selector de ciudad: mueve el mapa y cambia la zona del estado */}
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

        {showLayers && <LayersPanel layers={LAYERS} visible={visible} onToggle={toggle} />}

        {/* Botón reportar flotante (solo desktop; en móvil va dentro del panel) */}
        <Button
          variant="destructive"
          className="absolute bottom-6 left-4 z-[610] hidden rounded-xl shadow-xl sm:inline-flex"
        >
          <Plus className="h-[18px] w-[18px]" />
          Reportar
        </Button>

        <StatusPanel
          depto={depto}
          porGps={porGps}
          local={p.local}
          pais={p.pais}
          nivelLocal={p.nivelLocal}
          cuantasAqui={p.cuantasAqui}
          cuantasFuera={p.cuantasFuera}
          enfen={p.enfen}
          mar={p.mar}
          pacifico={p.pacifico}
          lluvia={p.lluvia}
          avisos={p.avisos}
          alertasCargadas={p.alertas != null}
          actualizado={p.actualizado}
          desactualizado={p.desactualizado}
        />
      </main>
    </div>
  );
}
