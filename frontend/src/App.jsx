import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronRight, Layers, LocateFixed, Plus, ShieldAlert } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import MapView from "@/components/MapView";
import LayersPanel from "@/components/LayersPanel";
import StatusPanel from "@/components/StatusPanel";
import ElNinoPanel from "@/components/ElNinoPanel";
import ErrorBoundary from "@/components/ErrorBoundary";
import CitySelector from "@/components/CitySelector";
import DiaSelector from "@/components/DiaSelector";
import ChipNowcast from "@/components/ChipNowcast";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { CITIES, DEFAULT_CITY, nearestCity } from "@/data/cities";
import { LAYERS } from "@/map/layers";
import { NIVEL } from "@/lib/nivel";
import { ENFEN_HEX } from "@/map/palette";
import { departamentoEn } from "@/lib/ubicacion";
import { centroCiudad, fechaDeOpcion } from "@/lib/pronostico";
import { usePanorama } from "@/hooks/usePanorama";
import { useGeolocation } from "@/hooks/useGeolocation";
import { useLayerVisibility } from "@/hooks/useLayerVisibility";
import { usePronosticoLocal } from "@/hooks/usePronosticoLocal";

const NOWCAST_OTRO_DIA = { texto: "El nowcasting es solo para las próximas 2 horas: elige Hoy." };

export default function App() {
  const { visible, toggle, mostrar, opciones, elegir } = useLayerVisibility(LAYERS);
  // Día elegido para los avisos y el pronóstico (opción vinculada); el nowcasting solo va con "Hoy".
  const dia = opciones.avisos ?? "ahora";
  const visibleMapa = useMemo(() => ({ ...visible, nowcast: visible.nowcast && dia === "ahora" }), [visible, dia]);
  // Texto corto de cada capa encendida (qué muestra, de cuándo es el dato o si falló).
  const [notas, setNotas] = useState({});
  const notasPanel = useMemo(() => (dia === "ahora" ? notas : { ...notas, nowcast: NOWCAST_OTRO_DIA }), [notas, dia]);
  const onNota = useCallback((id, texto) => setNotas((n) => (n[id] === texto ? n : { ...n, [id]: texto })), []);
  const [showLayers, setShowLayers] = useState(false);
  const [showElNino, setShowElNino] = useState(false);
  // capa a traer a la vista en el panel de capas; `vez` cambia en cada pedido, así un segundo
  // "ver evento" con el panel ya abierto vuelve a desplazarlo
  const [destacar, setDestacar] = useState({ id: null, vez: 0 });
  const cerrarElNino = useCallback(() => setShowElNino(false), []);
  const [city, setCity] = useState(DEFAULT_CITY.name);
  const [focus, setFocus] = useState({ lat: DEFAULT_CITY.lat, lon: DEFAULT_CITY.lon, zoom: 14 });
  const { pos: userPos, locate } = useGeolocation();
  // Zona del usuario: el departamento de la ciudad elegida o el de su GPS.
  const [depto, setDepto] = useState(DEFAULT_CITY.depto);
  const [porGps, setPorGps] = useState(false);
  const p = usePanorama(depto);
  // Pronóstico de SENAMHI de tu localidad (franja de 3 días) y su disco marcado en el mapa.
  const ciudad = useMemo(() => CITIES.find((c) => c.name === city) ?? DEFAULT_CITY, [city]);
  const pron = usePronosticoLocal({ ciudad, porGps, userPos });
  const codigoLocal = pron.estado !== "lejos" ? pron.localidad?.codigo ?? null : null;
  const localidadUsuario = useMemo(() => ({ codigo: codigoLocal, departamento: depto }), [codigoLocal, depto]);
  // Al elegir ciudad (y al arrancar) el mapa se corre hacia el punto de su localidad del pronóstico
  // (lib/pronostico.js centroCiudad), para que el disco de tu localidad se vea; el zoom no cambia.
  // Solo si el foco sigue en la ciudad (no con GPS ni tras "ver evento"), y una vez.
  const locLat = porGps ? null : pron.localidad?.lat ?? null;
  const locLon = porGps ? null : pron.localidad?.lon ?? null;
  useEffect(() => {
    if (porGps || focus.lat !== ciudad.lat || focus.lon !== ciudad.lon) return;
    const c = centroCiudad(ciudad, { lat: locLat, lon: locLon });
    if (c.lat !== focus.lat || c.lon !== focus.lon) setFocus({ ...c, zoom: focus.zoom });
  }, [focus, ciudad, porGps, locLat, locLon]);
  // Más angosto que lg, la columna izquierda baja hasta el selector de día (~188 px) o el chip del
  // nowcasting (~228 px): en pantallas bajas el panel de estado se acorta para no taparlos.
  const topePanel = visible.nowcast
    ? "max-lg:max-h-[min(70vh,calc(100vh-16rem))]"
    : visible.avisos || visible.pronostico
      ? "max-lg:max-h-[min(70vh,calc(100vh-13.5rem))]"
      : undefined;
  const abrirNowcast = () => {
    setShowLayers(true);
    setDestacar((d) => ({ id: "nowcast", vez: d.vez + 1 }));
  };

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

  // Desde el panel El Niño: prende la capa de eventos pasados con ese evento y encuadra el norte.
  const verEvento = (evento) => {
    elegir("fen", evento);
    mostrar("fen");
    setFocus({ lat: -7.2, lon: -78.8, zoom: 6 });
    setShowElNino(false);
    setDestacar((d) => ({ id: "fen", vez: d.vez + 1 }));
    setShowLayers(true);
  };

  const nv = NIVEL[p.nivelLocal];

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        active="mapa"
        depto={depto}
        nivel={p.nivelLocal}
        etiqueta={p.etiquetaLocal}
        alertCount={p.cuantasTotal}
        enfen={p.enfen}
        mar={p.mar}
        pacifico={p.pacifico}
        actualizado={p.actualizado}
        desactualizado={p.desactualizado}
        sinConexion={p.sinConexion}
        onElNino={() => setShowElNino(true)}
      />

      <main className="relative flex-1 h-screen">
        <MapView
          layers={LAYERS}
          visible={visibleMapa}
          opciones={opciones}
          focus={focus}
          userPos={userPos}
          onNota={onNota}
          localidadUsuario={localidadUsuario}
        />

        {/* Chip de marca + estado. No pasa bajo los botones de la derecha: en un celular angosto
            la letra baja un poco y, si aún no cabe ("Atentos a la lluvia en Madre de Dios"), se corta.
            Desde lg deja libre el centro de arriba para el selector de día. */}
        <div
          data-tapa-mapa="arriba"
          className="absolute left-4 top-4 z-[600] flex max-w-[calc(100%-5rem)] items-center gap-1.5 rounded-full border border-border bg-card/85 px-3 py-1.5 text-[0.8rem] font-semibold shadow-lg backdrop-blur sm:gap-2 sm:px-3.5 sm:text-sm lg:max-w-[calc(50%-9.5rem)]"
        >
          <span className="shrink-0 text-primary">SIMPAC</span>
          <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${nv.dot}`} />
          <span className={`min-w-0 truncate ${nv.text}`} title={`${p.etiquetaLocal ?? nv.label} en ${depto}`}>
            {p.etiquetaLocal ?? nv.label} en {depto}
          </span>
        </div>

        {/* Selector de ciudad (mueve el mapa y cambia la zona del estado) y El Niño en gráficos */}
        <div data-tapa-mapa="arriba" className="absolute left-4 top-[60px] z-[600] flex flex-col items-start gap-2">
          <CitySelector value={city} onChange={pickCity} />
          <button
            type="button"
            onClick={() => setShowElNino(true)}
            className="flex items-center gap-2 rounded-full border border-border bg-card/90 py-1 pl-1 pr-3 text-sm shadow-lg backdrop-blur hover:bg-accent"
          >
            <span
              className="grid h-7 w-7 place-items-center rounded-full text-white"
              style={{ background: ENFEN_HEX[p.enfen?.corto] ?? "#9CA3AF" }}
            >
              <ShieldAlert className="h-4 w-4" />
            </span>
            <span className="leading-tight">
              <span className="block text-[0.62rem] uppercase tracking-wider text-muted-foreground">
                {p.enfen?.quien ?? "El Niño costero"}
              </span>
              <span className="font-semibold">{p.enfen?.corto ?? "Sin dato"}</span>
            </span>
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          </button>
          {/* más angosto que lg: el día y el chip del nowcasting van en esta columna */}
          {(visible.avisos || visible.pronostico) && (
            <DiaSelector valor={dia} onCambiar={(v) => elegir("avisos", v)} className="lg:hidden" />
          )}
          {visible.nowcast && (
            <ChipNowcast
              nota={notas.nowcast}
              dia={dia}
              onAbrir={abrirNowcast}
              className="max-w-[min(26rem,calc(100vw-6rem))] lg:hidden"
            />
          )}
        </div>

        {/* lg: el día arriba al centro y, debajo, el chip del nowcasting (a la altura del selector de
            ciudad: su ancho deja libre la columna izquierda, 16 + 190 px y aire, a cada lado) */}
        {(visible.avisos || visible.pronostico) && (
          <div data-tapa-mapa="arriba" className="absolute left-1/2 top-4 z-[600] hidden -translate-x-1/2 lg:block">
            <DiaSelector valor={dia} onCambiar={(v) => elegir("avisos", v)} />
          </div>
        )}
        {visible.nowcast && (
          <div data-tapa-mapa="arriba" className="absolute left-1/2 top-[64px] z-[600] hidden max-w-[min(26rem,calc(100%-27rem))] -translate-x-1/2 lg:block">
            <ChipNowcast nota={notas.nowcast} dia={dia} onAbrir={abrirNowcast} />
          </div>
        )}

        {/* Herramientas */}
        <TooltipProvider delayDuration={200}>
          <div data-tapa-mapa="arriba" className="absolute right-4 top-4 z-[600] flex flex-col gap-2">
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

        {showLayers && (
          <LayersPanel
            layers={LAYERS}
            visible={visible}
            opciones={opciones}
            notas={notasPanel}
            destacar={destacar}
            onToggle={toggle}
            onOpcion={elegir}
          />
        )}

        {showElNino && (
          <ErrorBoundary
            fallback={
              <div className="absolute inset-x-4 top-4 z-[1100] mx-auto flex max-w-md items-center gap-3 rounded-xl border border-border bg-card p-4 text-sm shadow-2xl">
                No se pudo mostrar el panel de El Niño en este navegador.
                <Button variant="secondary" size="sm" className="ml-auto" onClick={cerrarElNino}>
                  Cerrar
                </Button>
              </div>
            }
          >
            <ElNinoPanel
              enfen={p.enfen}
              mar={p.mar}
              icen={p.icen}
              icenTmp={p.icenTmp}
              onVerEvento={verEvento}
              onCerrar={cerrarElNino}
            />
          </ErrorBoundary>
        )}

        {/* Botón reportar flotante (solo en pantallas anchas: más angosto chocaría con el panel de estado) */}
        <Button
          variant="destructive"
          className="absolute bottom-6 left-4 z-[610] hidden rounded-xl shadow-xl 2xl:inline-flex"
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
          etiqueta={p.etiquetaLocal}
          cuantasAqui={p.cuantasAqui}
          cuantasFuera={p.cuantasFuera}
          cuantasTotal={p.cuantasTotal}
          enfen={p.enfen}
          mar={p.mar}
          pacifico={p.pacifico}
          lluvia={p.lluvia}
          avisos={p.avisos}
          avisosZona={p.avisosAqui}
          lluviaZona={p.lluviaAqui}
          nivelOficialAqui={p.nivelOficialAqui}
          alertasCargadas={p.alertas != null}
          actualizado={p.actualizado}
          desactualizado={p.desactualizado}
          lluviaActualizada={p.lluviaActualizada}
          lluviaDesactualizada={p.lluviaDesactualizada}
          pron={pron}
          fechaMapa={visible.pronostico || visible.avisos ? fechaDeOpcion(dia) : null}
          tope={topePanel}
        />
      </main>
    </div>
  );
}
