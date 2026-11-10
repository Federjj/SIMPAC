import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Layers, LocateFixed, Plus, TriangleAlert } from "lucide-react";
import MapView from "@/components/MapView";
import LayersPanel from "@/components/LayersPanel";
import StatusPanel from "@/components/StatusPanel";
import ElNinoPanel from "@/components/ElNinoPanel";
import ErrorBoundary from "@/components/ErrorBoundary";
import CitySelector from "@/components/CitySelector";
import DiaSelector from "@/components/DiaSelector";
import ChipNowcast from "@/components/ChipNowcast";
import OnboardingGps from "@/components/OnboardingGps";
import { copiarTexto } from "@/components/TelefonoCopiable";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { LAYERS } from "@/map/layers";
import { NIVEL } from "@/lib/nivel";
import { cn } from "@/lib/utils";
import { fechaDeOpcion } from "@/lib/pronostico";
import { useZonaAhora } from "@/hooks/useZonaAhora";
import { ETIQUETA_NIVEL, cajaTuYRio, esFuerte, gpsVisto } from "@/lib/zonaAhora";

const NOWCAST_OTRO_DIA = { texto: "El nowcasting es solo para las próximas 2 horas: elige Hoy." };

// La página del mapa: lo que antes era App.jsx entero. El estado que comparten las otras páginas
// (capas, ciudad, zona, panorama, ríos vigilados, posición) vive en App y llega por props; aquí
// queda solo lo propio de esta pantalla (paneles abiertos, notas de las capas, la hoja "Tu zona
// ahora" y el modo emergencia). MapView nunca se desmonta al cambiar de ruta: las demás páginas se
// dibujan encima o al costado.
export default function Mapa({
  visible,
  visibleMapa,
  toggle,
  mostrar,
  opciones,
  elegir,
  nuevas,
  conocerTodas,
  cambios,
  restablecer,
  dondeGuarda,
  dia,
  city,
  pickCity,
  focus,
  setFocus,
  userPos,
  gpsStatus,
  geolocate,
  ciudad,
  depto,
  porGps,
  p,
  rios,
  pron,
  localidadUsuario,
  verRio,
}) {
  const navigate = useNavigate();
  // Texto corto de cada capa encendida (qué muestra, de cuándo es el dato o si falló).
  const [notas, setNotas] = useState({});
  const notasPanel = useMemo(() => (dia === "ahora" ? notas : { ...notas, nowcast: NOWCAST_OTRO_DIA }), [notas, dia]);
  const onNota = useCallback((id, texto) => setNotas((n) => (n[id] === texto ? n : { ...n, [id]: texto })), []);
  const [showLayers, setShowLayers] = useState(false);
  // al cerrar el panel de capas, las capas nuevas pasan a conocidas (deja de verse "Nueva")
  const capasAbiertas = useRef(false);
  useEffect(() => {
    if (capasAbiertas.current && !showLayers) conocerTodas();
    capasAbiertas.current = showLayers;
  }, [showLayers, conocerTodas]);
  const [showElNino, setShowElNino] = useState(false);
  // capa a traer a la vista en el panel de capas; `vez` cambia en cada pedido, así un segundo
  // "ver evento" con el panel ya abierto vuelve a desplazarlo
  const [destacar, setDestacar] = useState({ id: null, vez: 0 });
  const cerrarElNino = useCallback(() => setShowElNino(false), []);
  // la barra lateral pide abrir El Niño navegando a "/" con state.elNino (un número distinto cada vez)
  const pedidoElNino = useLocation().state?.elNino;
  useEffect(() => {
    if (pedidoElNino) setShowElNino(true);
  }, [pedidoElNino]);
  // Más angosto que lg, la columna izquierda baja hasta el chip del nowcasting (~140 px): en
  // pantallas bajas la hoja se acorta para no taparlo. (El selector de día vive en la hoja.)
  const topePanel = visible.nowcast ? "max-lg:max-h-[min(66vh,calc(100vh-12rem))]" : undefined;
  const abrirNowcast = () => {
    setShowLayers(true);
    setDestacar((d) => ({ id: "nowcast", vez: d.vez + 1 }));
  };

  // Desde el panel El Niño: prende la capa de eventos pasados con ese evento y encuadra el norte.
  const verEvento = (evento) => {
    elegir("fen", evento);
    mostrar("fen");
    setFocus({ lat: -7.2, lon: -78.8, zoom: 6 });
    setShowElNino(false);
    setDestacar((d) => ({ id: "fen", vez: d.vez + 1 }));
    setShowLayers(true);
  };

  // Enlaces internos dentro de los popups de Leaflet (<a data-ruta href="/historico?...">): se
  // navegan sin recargar la página. Leaflet corta la propagación del clic en el popup, así que se
  // escucha en captura, antes de que lo haga.
  useEffect(() => {
    const alClic = (e) => {
      const tel = e.target?.closest?.("a[data-copiar]");
      if (tel) {
        e.preventDefault();
        const texto = tel.getAttribute("data-copiar");
        const original = tel.textContent;
        copiarTexto(texto).then((ok) => {
          if (!ok) return;
          tel.textContent = "Copiado";
          setTimeout(() => (tel.textContent = original), 1800);
        });
        return;
      }
      const a = e.target?.closest?.("a[data-ruta]");
      if (!a) return;
      e.preventDefault();
      navigate(a.getAttribute("href"));
    };
    document.addEventListener("click", alClic, true);
    return () => document.removeEventListener("click", alClic, true);
  }, [navigate]);

  const reportar = () => navigate("/comunidad/nuevo");
  const verAlertas = () => navigate("/alertas");

  // "Tu zona ahora": nivel máximo (alerta_actual + ríos vigilados), titular corto, distancias al
  // río y a la zona, botón por nivel (hooks/useZonaAhora.js)
  const zona = useZonaAhora({ p, rios, userPos, porGps, ciudad, depto });
  const zonaRef = useRef(zona);
  zonaRef.current = zona;
  const nivelMax = zona.nivel;
  const fuerte = esFuerte(nivelMax);
  const gps = useMemo(() => ({ status: gpsStatus, geolocate }), [gpsStatus, geolocate]);
  // pedidos a la hoja: { vez, altura, forzar, seccion }
  const [pedido, setPedido] = useState(null);
  // la hoja "Tu zona ahora" va detrás de un botón flotante; cualquier pedido a la hoja la abre
  const [hojaAbierta, setHojaAbierta] = useState(false);
  const pedir = (altura, extra = {}) => {
    setHojaAbierta(true);
    setPedido({ vez: Date.now(), altura, ...extra });
  };

  // Modo emergencia: cuando la zona pasa a alerta o emergencia (por alerta_actual o por un río
  // vigilado), una vez por cambio de nivel: la hoja se pliega (forzado solo en emergencia: en
  // alerta se respeta si la persona la movió a mano) para que el cauce y la zona roja se vean, se
  // prenden el río y su zona y se encuadra el cauce. El nivel va en <html data-nivel> para que el pulso de tu ubicación y
  // del río sigan (index.css). Nunca se cierra solo: la información no se borra por una fuente caída.
  const nivelPrevio = useRef(null);
  useEffect(() => {
    document.documentElement.dataset.nivel = nivelMax;
    if (nivelPrevio.current === nivelMax) return;
    const antes = nivelPrevio.current;
    nivelPrevio.current = nivelMax;
    if (!esFuerte(nivelMax)) return;
    // de alerta a emergencia (o al revés) también se vuelve a abrir
    if (antes === nivelMax) return;
    // la hoja no se abre sola: el botón "Alertas" ya toma el color del nivel y el cauce se ve
    mostrar("rio");
    mostrar("zona");
    const rio = zonaRef.current.principal?.rio;
    if (rio) verRio(rio);
  }, [nivelMax, mostrar, verRio]);
  useEffect(() => () => delete document.documentElement.dataset.nivel, []);

  // El botón del nivel de "Tu zona ahora": lo que lleva al mapa pliega la hoja (en el celular
  // abierta lo tapa) y después encuadra
  const accion = (que) => {
    const z = zonaRef.current;
    const rio = z.principal?.rio ?? null;
    if (que === "zona") {
      setHojaAbierta(false);
      mostrar("rio");
      mostrar("zona");
      const caja = cajaTuYRio(z.origen, rio?.cauce);
      if (caja) setFocus({ lat: z.origen[0], lon: z.origen[1], zoom: 16, bounds: caja });
      else if (rio) verRio(rio);
      else if (z.origen) setFocus({ lat: z.origen[0], lon: z.origen[1], zoom: 14 });
    } else if (que === "pasar") {
      setHojaAbierta(false);
      if (rio) verRio(rio);
      mostrar("desbordes");
    } else if (que === "acudir") {
      mostrar("acudir");
      pedir("media", { forzar: true, seccion: "acudir" });
    } else if (que === "avisos") {
      setHojaAbierta(false);
      mostrar("avisos");
      if (ciudad) setFocus({ lat: ciudad.lat, lon: ciudad.lon, zoom: 8 });
    }
  };

  // Desde "A dónde acudir": enciende la capa y encuadra tu punto y el destino (línea recta, no ruta).
  const verPunto = useCallback(
    ({ lat, lon }) => {
      mostrar("acudir");
      const o = zonaRef.current.origen;
      if (o) {
        const caja = [
          [Math.min(o[0], lat), Math.min(o[1], lon)],
          [Math.max(o[0], lat), Math.max(o[1], lon)],
        ];
        setFocus({ lat, lon, zoom: 16, bounds: caja });
      } else {
        setFocus({ lat, lon, zoom: 16 });
      }
    },
    [mostrar, setFocus]
  );

  // Bienvenida del GPS: una vez, antes de pedir el permiso; no sale si ya se vio, si no hay GPS en
  // el navegador o si el permiso ya estaba concedido (App pide la ubicación solo) o denegado.
  // (solo en desarrollo, ?bienvenida=1 la fuerza para mirarla aunque el permiso ya esté decidido)
  const forzada = import.meta.env.DEV && new URLSearchParams(window.location.search).has("bienvenida");
  const [bienvenida, setBienvenida] = useState(() => forzada || (!gpsVisto() && typeof navigator !== "undefined" && Boolean(navigator.geolocation)));
  useEffect(() => {
    if (!bienvenida || forzada) return undefined;
    let vivo = true;
    try {
      navigator.permissions
        ?.query({ name: "geolocation" })
        .then((r) => vivo && r.state !== "prompt" && setBienvenida(false))
        .catch(() => {});
    } catch {
      /* sin Permissions API: se muestra igual */
    }
    return () => {
      vivo = false;
    };
  }, [bienvenida]);
  useEffect(() => {
    if (userPos && !forzada) setBienvenida(false);
  }, [userPos, forzada]);

  // chip de arriba: hereda el nivel máximo (incluido el río), con fondo fuerte en alerta y emergencia
  const etiquetaChip =
    nivelMax !== p.nivelLocal ? (nivelMax === "aviso" ? "Atentos" : nivelMax === "sin_dato" ? NIVEL.sin_dato.label : ETIQUETA_NIVEL[nivelMax]) : p.etiquetaLocal ?? NIVEL[p.nivelLocal].label;

  return (
    <>
      <MapView
        layers={LAYERS}
        visible={visibleMapa}
        opciones={opciones}
        focus={focus}
        userPos={userPos}
        onNota={onNota}
        localidadUsuario={localidadUsuario}
      />

      {/* Chip de marca + estado: el nivel más alto de la zona contando el río vigilado. En alerta y
          emergencia va con fondo del nivel y texto blanco. No pasa bajo los botones de la derecha;
          desde lg deja libre el centro de arriba para el selector de día. */}
      <div
        data-tapa-mapa="arriba"
        className={cn(
          "chip-estado absolute left-4 top-4 z-[600] flex max-w-[calc(100%-5rem)] items-center gap-1.5 rounded-full border px-3 py-1.5 text-[0.8rem] font-semibold shadow-lg backdrop-blur sm:gap-2 sm:px-3.5 sm:text-sm lg:max-w-[calc(50%-9.5rem)]",
          `tz-${nivelMax}`,
          fuerte ? "tz-relleno border-transparent" : "border-border bg-card/85"
        )}
        role="status"
      >
        <span className={cn("min-w-0 truncate", !fuerte && "tz-tinta", fuerte && "uppercase tracking-wide")} title={`${etiquetaChip} en ${depto}`}>
          {etiquetaChip} en {depto}
        </span>
      </div>

      {/* Selector de ciudad (mueve el mapa y cambia la zona del estado); más angosto que lg, debajo
          el chip del nowcasting. El día y El Niño viven en la hoja (en escritorio, arriba al centro
          y en la barra lateral). */}
      <div data-tapa-mapa="arriba" className="absolute left-4 top-[60px] z-[600] flex flex-col items-start gap-2">
        <CitySelector value={city} onChange={pickCity} />
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
                aria-label="Capas del mapa"
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
                aria-label="Mi ubicación"
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
          nuevas={nuevas}
          cambios={cambios}
          dondeGuarda={dondeGuarda}
          onToggle={toggle}
          onOpcion={elegir}
          onRestablecer={restablecer}
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

      {/* Botón reportar flotante (desde lg, bajo las herramientas de la derecha: la hoja ocupa la
          esquina de abajo a la izquierda; más angosto va dentro de la hoja). Se retira mientras el
          panel de capas está abierto: el panel arranca a 70 px del borde derecho y el botón, más
          ancho que la columna de herramientas, quedaba encima de sus interruptores (el de Avisos
          de SENAMHI entre ellos). Vuelve al cerrar el panel con el botón de capas. */}
      {!showLayers && (
        <Button
          variant="destructive"
          className="absolute right-4 top-[6.25rem] z-[610] hidden rounded-xl shadow-xl lg:inline-flex"
          onClick={reportar}
        >
          <Plus className="h-[18px] w-[18px]" />
          Reportar
        </Button>
      )}

      {bienvenida ? (
        <OnboardingGps
          ciudad={ciudad}
          city={city}
          pickCity={pickCity}
          geolocate={geolocate}
          status={gpsStatus}
          onCerrar={() => setBienvenida(false)}
        />
      ) : !hojaAbierta ? (
        <button
          type="button"
          data-tapa-mapa="abajo"
          onClick={() => setHojaAbierta(true)}
          className={cn(
            "tz-boton-alertas absolute bottom-4 left-4 z-[600] flex items-center gap-2 rounded-full border px-4 py-2.5 text-sm font-semibold shadow-xl backdrop-blur",
            `tz-${nivelMax}`,
            fuerte ? "tz-relleno border-transparent" : "border-border bg-card/90"
          )}
          aria-label={`Ver alertas: ${etiquetaChip} en ${depto}`}
        >
          <TriangleAlert className="h-[18px] w-[18px]" />
          Alertas
          {p.cuantasTotal > 0 && (
            <span className="grid h-5 min-w-5 place-items-center rounded-full bg-destructive px-1.5 text-xs text-destructive-foreground">{p.cuantasTotal}</span>
          )}
        </button>
      ) : (
        <StatusPanel
          onCerrar={() => setHojaAbierta(false)}
          p={p}
          zona={zona}
          depto={depto}
          ciudad={ciudad}
          gps={gps}
          pron={pron}
          fechaMapa={visible.pronostico || visible.avisos ? fechaDeOpcion(dia) : null}
          rios={rios}
          dia={dia}
          elegir={elegir}
          conDia={Boolean(visible.avisos || visible.pronostico)}
          onElNino={() => setShowElNino(true)}
          onVerRio={verRio}
          onAccion={accion}
          verPunto={verPunto}
          pedido={pedido}
          tope={topePanel}
          onReportar={reportar}
          onVerAlertas={verAlertas}
          onReintentar={p.refresh}
        />
      )}
    </>
  );
}
