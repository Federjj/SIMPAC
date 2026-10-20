import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Route, Routes, useLocation, useNavigate } from "react-router-dom";
import Sidebar from "@/components/Sidebar";
import BarraInferior from "@/components/BarraInferior";
import ErrorBoundary from "@/components/ErrorBoundary";
import { ContextoApp } from "@/components/ContextoApp";
import { Cargando, ErrorCarga } from "@/components/EstadoCarga";
import PanelPagina from "@/components/PanelPagina";
import Mapa from "@/pages/Mapa";
import { CITIES, DEFAULT_CITY, nearestCity } from "@/data/cities";
import { LAYERS } from "@/map/layers";
import { departamentoEn } from "@/lib/ubicacion";
import { centroCiudad } from "@/lib/pronostico";
import { guardarZonaLocal, leerZonaLocal } from "@/lib/sesion";
import { usePanorama } from "@/hooks/usePanorama";
import { useGeolocation } from "@/hooks/useGeolocation";
import { useLayerVisibility } from "@/hooks/useLayerVisibility";
import { usePronosticoLocal } from "@/hooks/usePronosticoLocal";
import { useRiosVigilados } from "@/hooks/useRiosVigilados";
import { SesionProvider, useSesion } from "@/hooks/useSesion";
import { ETIQUETA_NIVEL, nivelMaximo } from "@/lib/zonaAhora";

// Las páginas que no son el mapa se cargan cuando se entra a ellas (lazy): el mapa arranca igual
// de rápido que antes.
const Alertas = lazy(() => import("@/pages/Alertas"));
const Comunidad = lazy(() => import("@/pages/Comunidad"));
const ReporteNuevo = lazy(() => import("@/pages/ReporteNuevo"));
const ReporteDetalle = lazy(() => import("@/pages/ReporteDetalle"));
const Chat = lazy(() => import("@/pages/Chat"));
const Cuenta = lazy(() => import("@/pages/Cuenta"));
const Historico = lazy(() => import("@/pages/Historico"));

// true mientras la pantalla es más angosta que el corte lg de Tailwind (1024 px): ahí la página
// tapa el mapa entero. Desde lg van lado a lado y el mapa sigue usable.
const ANGOSTA = "(max-width: 1023.98px)";
function usePantallaAngosta() {
  const [angosta, setAngosta] = useState(() => {
    try {
      return window.matchMedia(ANGOSTA).matches;
    } catch {
      return false;
    }
  });
  useEffect(() => {
    let mq;
    try {
      mq = window.matchMedia(ANGOSTA);
    } catch {
      return undefined;
    }
    const al = () => setAngosta(mq.matches);
    al();
    mq.addEventListener("change", al);
    return () => mq.removeEventListener("change", al);
  }, []);
  return angosta;
}

// [[sur, oeste], [norte, este]] de una geometría GeoJSON (el cauce de un río vigilado), o null
function cajaGeo(g) {
  const pts = [];
  const juntar = (c) => (typeof c?.[0] === "number" ? pts.push(c) : c?.forEach(juntar));
  juntar(g?.coordinates);
  if (!pts.length) return null;
  const lons = pts.map((p) => p[0]);
  const lats = pts.map((p) => p[1]);
  return [
    [Math.min(...lats), Math.min(...lons)],
    [Math.max(...lats), Math.max(...lons)],
  ];
}

export default function App() {
  return (
    <SesionProvider>
      <Marco />
    </SesionProvider>
  );
}

// El marco: barra lateral (md+), barra inferior (menos de md), el mapa siempre montado y, cuando
// la ruta no es "/", la página encima del mapa (celular) o en una columna a su lado (desde lg).
function Marco() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { perfil } = useSesion();
  // capas encendidas y opciones, recordadas en este navegador (o en la cuenta, con sesión)
  const { visible, toggle, mostrar, opciones, elegir, nuevas, conocerTodas, cambios, restablecer, dondeGuarda } =
    useLayerVisibility(LAYERS);
  // Día elegido para los avisos y el pronóstico (opción vinculada); el nowcasting solo va con "Hoy".
  const dia = opciones.avisos ?? "ahora";
  const visibleMapa = useMemo(() => ({ ...visible, nowcast: visible.nowcast && dia === "ahora" }), [visible, dia]);
  // la ciudad por defecto recordada en este navegador (Cuenta > Mi zona), si no, Cajamarca
  const [city, setCity] = useState(() => leerZonaLocal() ?? DEFAULT_CITY.name);
  const inicial = CITIES.find((c) => c.name === city) ?? DEFAULT_CITY;
  const [focus, setFocus] = useState({ lat: inicial.lat, lon: inicial.lon, zoom: 14 });
  const { pos: userPos, status: gpsStatus, locate } = useGeolocation();
  // Zona del usuario: el departamento de la ciudad elegida o el de su GPS.
  const [depto, setDepto] = useState(inicial.depto);
  const [porGps, setPorGps] = useState(false);
  const p = usePanorama(depto);
  // ríos vigilados de la zona con el nivel de su zona (panel de estado; no cambian el contador)
  const rios = useRiosVigilados(depto);
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

  const pickCity = useCallback((name) => {
    const c = CITIES.find((x) => x.name === name) || DEFAULT_CITY;
    setCity(c.name);
    setDepto(c.depto);
    setPorGps(false);
    setFocus({ lat: c.lat, lon: c.lon, zoom: 14 });
  }, []);

  // Ubicación real (con permiso); si falla, el mapa se queda en la ciudad elegida.
  const geolocate = useCallback(async () => {
    const lugar = await locate();
    if (!lugar) return;
    const [lat, lon] = lugar;
    setFocus({ lat, lon, zoom: 15 });
    const cercana = nearestCity(lat, lon);
    setCity(cercana.name);
    setDepto((await departamentoEn(lat, lon).catch(() => null)) ?? cercana.depto);
    setPorGps(true);
  }, [locate]);

  // Al arrancar solo se usa el GPS si el navegador ya tenía el permiso concedido: nadie ve un pedido
  // de permiso sin explicación. La primera vez lo pide la pantalla de bienvenida del mapa
  // (components/OnboardingGps.jsx) o el botón "Mi ubicación".
  useEffect(() => {
    let vivo = true;
    try {
      navigator.permissions
        ?.query({ name: "geolocation" })
        .then((r) => vivo && r.state === "granted" && geolocate())
        .catch(() => {});
    } catch {
      /* navegador sin Permissions API: se queda en la ciudad hasta que la persona toque el botón */
    }
    return () => {
      vivo = false;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // "Mi zona" guardada en la cuenta: la primera vez que llega el perfil, si este navegador no tenía
  // una ciudad elegida y no se está usando el GPS, se toma la de la cuenta.
  const zonaAplicada = useRef(false);
  useEffect(() => {
    if (!perfil?.ciudad || zonaAplicada.current) return;
    zonaAplicada.current = true;
    if (leerZonaLocal() || porGps) return;
    pickCity(perfil.ciudad);
    guardarZonaLocal(perfil.ciudad);
  }, [perfil, porGps, pickCity]);

  // Desde el panel de estado (que se pliega): prende el río y sus zonas y encuadra el cauce entero
  // en lo que queda libre entre los chips de arriba y el panel (MapView), hasta zoom 14.
  const verRio = useCallback(
    (r) => {
      mostrar("rio");
      mostrar("zona");
      setFocus({ lat: r.centro_lat, lon: r.centro_lon, zoom: Math.max(r.zoom ?? 13, 14), bounds: cajaGeo(r.cauce) });
    },
    [mostrar]
  );

  // Para las páginas: volver al mapa centrado en un punto (un reporte) o en un río vigilado.
  const irAlMapa = useCallback(
    ({ lat, lon, zoom = 16 }) => {
      setFocus({ lat, lon, zoom });
      navigate("/");
    },
    [navigate]
  );
  const verRioEnMapa = useCallback(
    (r) => {
      verRio(r);
      navigate("/");
    },
    [verRio, navigate]
  );

  const contexto = useMemo(
    () => ({ depto, porGps, userPos, city, ciudad, pickCity, geolocate, p, rios, pron, irAlMapa, verRioEnMapa }),
    [depto, porGps, userPos, city, ciudad, pickCity, geolocate, p, rios, pron, irAlMapa, verRioEnMapa]
  );

  const enMapa = pathname === "/";
  // En el celular y la tablet la página tapa el mapa entero: el mapa se marca inerte (inert +
  // aria-hidden) para que el teclado y el lector de pantalla no lleguen a sus controles tapados
  // ("Elegir ciudad", "Capas", "A dónde acudir"...). Sigue montado y vivo; al volver a "/" se libera.
  const angosta = usePantallaAngosta();
  const mapaTapado = !enMapa && angosta;
  // la barra lateral muestra el nivel más alto de la zona contando el río vigilado (igual que el
  // chip del mapa y "Tu zona ahora"); en alerta o emergencia la etiqueta es la del semáforo
  const nivelMax = nivelMaximo(p.nivelLocal, rios);
  const etiquetaMax =
    nivelMax === p.nivelLocal ? p.etiquetaLocal : nivelMax === "aviso" ? "Atentos" : ETIQUETA_NIVEL[nivelMax].charAt(0) + ETIQUETA_NIVEL[nivelMax].slice(1).toLowerCase();

  return (
    <ContextoApp.Provider value={contexto}>
      <div className="flex h-screen overflow-hidden">
        <Sidebar
          depto={depto}
          nivel={nivelMax}
          etiqueta={etiquetaMax}
          alertCount={p.cuantasTotal}
          enfen={p.enfen}
          mar={p.mar}
          pacifico={p.pacifico}
          actualizado={p.actualizado}
          desactualizado={p.desactualizado}
          sinConexion={p.sinConexion}
          onElNino={() => navigate("/", { state: { elNino: Date.now() } })}
        />

        <div className="flex min-w-0 flex-1 flex-col">
          <div className="relative flex min-h-0 flex-1">
            {/* La página actual: a pantalla completa sobre el mapa en el celular y la tablet, y
                como columna junto al mapa desde lg. El mapa de abajo sigue montado y vivo. */}
            {!enMapa && (
              <section
                aria-label="Página"
                className="absolute inset-0 z-[1200] flex min-h-0 flex-col bg-background lg:static lg:z-auto lg:w-[28rem] lg:flex-none lg:border-r lg:border-border xl:w-[30rem]"
              >
                <ErrorBoundary
                  fallback={
                    <PanelPagina titulo="Algo salió mal">
                      <ErrorCarga texto="Esta página no se pudo mostrar en este navegador." onReintentar={() => window.location.reload()} />
                    </PanelPagina>
                  }
                >
                  <Suspense fallback={<PanelPagina titulo="Cargando"><Cargando /></PanelPagina>}>
                    <Routes>
                      <Route path="/alertas" element={<Alertas />} />
                      <Route path="/comunidad" element={<Comunidad />} />
                      <Route path="/comunidad/nuevo" element={<ReporteNuevo />} />
                      <Route path="/comunidad/:id" element={<ReporteDetalle />} />
                      <Route path="/chat" element={<Chat />} />
                      <Route path="/cuenta/*" element={<Cuenta />} />
                      <Route path="/historico" element={<Historico />} />
                      <Route path="*" element={<NoEncontrada />} />
                    </Routes>
                  </Suspense>
                </ErrorBoundary>
              </section>
            )}

            <main
              className="relative min-w-0 flex-1"
              aria-label="Mapa"
              aria-hidden={mapaTapado || undefined}
              // React 18 no conoce `inert` como booleano: "" lo pone y undefined lo quita
              inert={mapaTapado ? "" : undefined}
            >
              <Mapa
                visible={visible}
                visibleMapa={visibleMapa}
                toggle={toggle}
                mostrar={mostrar}
                opciones={opciones}
                elegir={elegir}
                nuevas={nuevas}
                conocerTodas={conocerTodas}
                cambios={cambios}
                restablecer={restablecer}
                dondeGuarda={dondeGuarda}
                dia={dia}
                city={city}
                pickCity={pickCity}
                focus={focus}
                setFocus={setFocus}
                userPos={userPos}
                gpsStatus={gpsStatus}
                geolocate={geolocate}
                ciudad={ciudad}
                depto={depto}
                porGps={porGps}
                p={p}
                rios={rios}
                pron={pron}
                localidadUsuario={localidadUsuario}
                verRio={verRio}
              />
            </main>
          </div>
          <BarraInferior alertCount={p.cuantasTotal} />
        </div>
      </div>
    </ContextoApp.Provider>
  );
}

function NoEncontrada() {
  return (
    <PanelPagina titulo="Esta página no existe">
      <p className="text-sm text-muted-foreground">Revisa la dirección o vuelve al mapa.</p>
    </PanelPagina>
  );
}
