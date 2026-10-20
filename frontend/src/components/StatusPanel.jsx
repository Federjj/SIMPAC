import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronRight, ChevronUp, Droplets, LifeBuoy, Megaphone, Plus, ShieldAlert, TriangleAlert, Waves } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { NIVEL_HEX, ZONA_HEX, ENFEN_HEX } from "@/map/palette";
import { fraseCorta } from "@/lib/zonaRio";
import { ATRIBUCION_SENAMHI } from "@/map/senamhi";
import FranjaPronostico from "@/components/FranjaPronostico";
import DiaSelector from "@/components/DiaSelector";
import TuZona from "@/components/TuZona";
import MedidorCaudal from "@/components/MedidorCaudal";
import BarrasLluvia from "@/components/BarrasLluvia";
import AcudirCercanos from "@/components/AcudirCercanos";
import { useAltoHoja } from "@/hooks/useAltoHoja";

const COLOR_AVISO = { aviso: "amarillo", alerta: "naranja", emergencia: "rojo" };
const URL_AVISO = (referencia) =>
  referencia === "SENAMHI lluvia 24h"
    ? "https://www.senamhi.gob.pe/?p=aviso-24H"
    : "https://www.senamhi.gob.pe/?p=aviso-meteorologico";

// Las cuatro alturas de la hoja (Material: hoja estándar expansible; el mapa sigue vivo detrás):
//   plegado   lo mínimo para leer en 5 segundos: semáforo, titular, instrucción (en alerta o
//             emergencia), fuente y hora y el botón del nivel (~200-280 px: el mapa queda a la vista)
//   vistazo   + chips de distancia al río y a la zona, cómo activar el GPS y el pie
//   media     + los gráficos vivos: medidor del río, lluvia cerca de ti, a dónde acudir, pronóstico
//   completa  + avisos de SENAMHI, ríos con señales, resto del país, El Niño, "Qué significa esto",
//             Reportar, Ver alertas y la atribución literal de SENAMHI
// En el celular la hoja arranca plegada y el modo emergencia y "ver en el mapa" la pliegan (antes el
// "vistazo" ocupaba el 61 % de la pantalla y el mapa quedaba casi invisible); desde lg es una tarjeta
// a la izquierda que no tapa el mapa y arranca en "vistazo".
export const ALTURAS = ["plegado", "vistazo", "media", "completa"];
const ARRASTRE_PX = 40; // cuánto hay que arrastrar el asa para cambiar de altura
const esEscritorio = () => typeof window !== "undefined" && Boolean(window.matchMedia?.("(min-width: 1024px)").matches);
// la altura más chica que tiene sentido en esta pantalla
const minima = () => (esEscritorio() ? "vistazo" : "plegado");

function Explica({ titulo, children, pie, aviso }) {
  return (
    <div className="text-sm leading-snug">
      <span className="font-semibold">{titulo}</span> {children}
      {aviso && <span className="block text-xs text-nivel-alerta">{aviso}</span>}
      {pie && <span className="block text-xs text-muted-foreground">{pie}</span>}
    </div>
  );
}

function Titulo({ children }) {
  return <h3 className="text-[0.68rem] uppercase tracking-wider text-muted-foreground">{children}</h3>;
}

export default function StatusPanel({
  p, // usePanorama(depto)
  zona, // useZonaAhora
  depto,
  ciudad, // la ciudad elegida (data/cities)
  gps, // { status, geolocate }
  pron,
  fechaMapa,
  rios = [], // ríos vigilados de la zona con el nivel de su zona: [{rio, estado}] (useRiosVigilados)
  dia,
  elegir,
  conDia = false, // si las capas de avisos o pronóstico están prendidas (el selector de día tiene sentido)
  onElNino, // () -> abre el panel de El Niño en gráficos
  onVerRio, // (rio) -> prende las capas del río y de sus zonas y lleva el mapa hasta él
  onAccion, // (accion) -> el botón del nivel (zona | pasar | acudir | avisos)
  verPunto, // ({lat, lon, clave}) -> centra el mapa en un punto de "A dónde acudir"
  pedido, // { vez, altura, forzar, seccion } desde Mapa (modo emergencia, botón del nivel)
  onAltura, // (altura) -> Mapa se entera (para el encuadre)
  tope, // clase de alto máximo en pantallas bajas (no tapar el chip del nowcasting)
  onReportar,
  onVerAlertas,
  onReintentar,
}) {
  const [altura, setAltura] = useState(minima);
  const [abierto, setAbierto] = useState(false); // "Qué significa esto"
  const aMano = useRef(false); // la persona cambió la altura: una alerta no la vuelve a abrir
  const hojaRef = useRef(null);
  const acudirRef = useRef(null);
  useAltoHoja(hojaRef);

  const cambiar = useCallback(
    (a, { mano = false } = {}) => {
      if (mano) aMano.current = true;
      setAltura(a);
      onAltura?.(a);
    },
    [onAltura]
  );
  const subir = () => cambiar(ALTURAS[Math.min(ALTURAS.length - 1, ALTURAS.indexOf(altura) + 1)], { mano: true });
  const bajar = () => cambiar(ALTURAS[Math.max(0, ALTURAS.indexOf(altura) - 1)], { mano: true });

  // pedidos desde Mapa: el modo emergencia pliega la hoja (forzado) una vez por cambio de nivel;
  // en alerta solo si la persona no la movió a mano; el botón "A dónde acudir" abre a "media".
  // Un pedido de "plegado" en escritorio vale "vistazo" (ahí la tarjeta no tapa el mapa).
  useEffect(() => {
    if (!pedido?.vez) return;
    const a = pedido.altura ?? "plegado";
    if (pedido.forzar || !aMano.current) setAltura(a === "plegado" ? minima() : a);
    if (pedido.seccion === "acudir") {
      setAltura("media");
      // la tarjeta recién se monta: se baja hasta ella en el cuadro siguiente
      requestAnimationFrame(() => acudirRef.current?.scrollIntoView({ block: "start", behavior: "smooth" }));
    }
  }, [pedido]);

  // "Ver en el mapa" pliega la hoja (abierta tapa el río) y lleva el mapa hasta el río
  const verRio = (rio) => {
    cambiar(minima(), { mano: true });
    onVerRio?.(rio);
  };
  // "Ver en el mapa" de un punto de "A dónde acudir": igual, primero se pliega
  const verPuntoPlegando = verPunto
    ? (punto) => {
        cambiar(minima(), { mano: true });
        verPunto(punto);
      }
    : undefined;

  // arrastre del asa con el puntero: la hoja sigue al dedo (transform) y al soltar sube o baja
  // una altura; las flechas hacen lo mismo con teclado
  const arrastre = useRef(null);
  const alBajarPuntero = (e) => {
    if (e.button != null && e.button !== 0) return;
    arrastre.current = { y0: e.clientY, dy: 0, id: e.pointerId };
    e.currentTarget.setPointerCapture?.(e.pointerId);
    hojaRef.current?.classList.add("arrastrando");
  };
  const alMoverPuntero = (e) => {
    const a = arrastre.current;
    if (!a || a.id !== e.pointerId) return;
    a.dy = e.clientY - a.y0;
    const dy = Math.max(-48, Math.min(96, a.dy));
    if (hojaRef.current) hojaRef.current.style.transform = `translateY(${dy}px)`;
  };
  const alSoltarPuntero = (e) => {
    const a = arrastre.current;
    if (!a || a.id !== e.pointerId) return;
    arrastre.current = null;
    if (hojaRef.current) {
      hojaRef.current.style.transform = "";
      hojaRef.current.classList.remove("arrastrando");
    }
    if (a.dy <= -ARRASTRE_PX) subir();
    else if (a.dy >= ARRASTRE_PX) bajar();
  };

  const nivel = zona?.nivel ?? "sin_dato";
  const fuerte = zona?.fuerte;
  const principal = zona?.principal ?? null;
  const riosConSenales = rios.filter((r) => r.estado.nivel !== "sin_senales");
  const avisosZona = p.avisosAqui ?? [];
  const lluviaZona = p.lluviaAqui ?? [];
  const masLluvia = lluviaZona.length - 3;
  const alertasCargadas = p.alertas != null;
  const total = p.cuantasTotal ?? 0;
  const origen = zona?.origen ?? null;
  const desdeTxt = zona?.porGps ? "desde tu ubicación" : `desde el centro de ${ciudad?.name ?? "la ciudad"} (activa tu ubicación para afinar)`;
  const botonVer = (rio) =>
    onVerRio && (
      <button type="button" onClick={() => verRio(rio)} className="whitespace-nowrap text-xs text-muted-foreground underline hover:text-foreground">
        Ver en el mapa
      </button>
    );

  const acudir = origen && (
    <section ref={acudirRef} className="scroll-mt-2 px-4 pt-3" aria-label="A dónde acudir">
      <Titulo>
        <span className="inline-flex items-center gap-1.5">
          <LifeBuoy className="h-3.5 w-3.5" aria-hidden="true" />
          A dónde acudir
        </span>
      </Titulo>
      <AcudirCercanos lat={origen[0]} lon={origen[1]} desde={desdeTxt} compacto onVerEnMapa={verPuntoPlegando} className="mt-1" />
    </section>
  );

  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-0 z-[600] lg:bottom-4 lg:left-4 lg:right-auto lg:w-[420px] lg:max-w-[calc(100%-2rem)]">
      <div
        ref={hojaRef}
        data-tapa-mapa="abajo"
        data-altura={altura}
        className={cn(
          "hoja hoja-entra pointer-events-auto relative flex flex-col overflow-hidden rounded-t-2xl border border-border bg-card/95 shadow-2xl backdrop-blur lg:rounded-2xl",
          `tz-${nivel}`,
          fuerte && "tz-suave",
          nivel === "emergencia" && "es-emergencia",
          // plegado cabe sin desplazar (~200-280 px); vistazo deja al menos la mitad del mapa libre
          altura === "plegado" && "max-h-[min(44vh,calc(100vh-9rem))]",
          altura === "vistazo" && "max-h-[min(50vh,calc(100vh-8rem))]",
          altura === "media" && "max-h-[min(66vh,calc(100vh-7rem))]",
          altura === "completa" && "max-h-[88vh]",
          "lg:max-h-[80vh]",
          // el tope por el chip del nowcasting solo importa abierta: plegada y en vistazo ya es más baja
          (altura === "media" || altura === "completa") && tope
        )}
      >
        <div className="hoja-franja shrink-0" aria-hidden="true" />
        {/* asa: arrastrar o tocar para cambiar de altura; las flechas son la versión con teclado */}
        <div className="flex shrink-0 items-center px-2">
          <div
            role="button"
            tabIndex={0}
            aria-label={`Cambiar el tamaño del panel (ahora: ${altura})`}
            className="hoja-arrastre flex flex-1 justify-center py-2"
            onPointerDown={alBajarPuntero}
            onPointerMove={alMoverPuntero}
            onPointerUp={alSoltarPuntero}
            onPointerCancel={alSoltarPuntero}
            onClick={() => (altura === "completa" ? cambiar(minima(), { mano: true }) : subir())}
            onKeyDown={(e) => {
              if (e.key === "ArrowUp") subir();
              else if (e.key === "ArrowDown") bajar();
              else if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                altura === "completa" ? cambiar(minima(), { mano: true }) : subir();
              }
            }}
          >
            <span className="hoja-asa" />
          </div>
          <div className="absolute right-2 top-2.5 flex items-center gap-0.5">
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={bajar} disabled={altura === ALTURAS[0]} aria-label="Achicar el panel">
              <ChevronDown className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={subir} disabled={altura === "completa"} aria-label="Agrandar el panel">
              <ChevronUp className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain pb-2">
          {zona && (
            <TuZona zona={zona} depto={depto} gps={gps} plegado={altura === "plegado"} onAccion={onAccion} onVerRio={onVerRio ? verRio : null} />
          )}
          {!alertasCargadas && onReintentar && /^No se pudo/.test(p.local ?? "") && (
            <div className="px-4 pt-1">
              <button type="button" onClick={onReintentar} className="text-sm font-medium text-muted-foreground underline hover:text-foreground">
                Reintentar
              </button>
            </div>
          )}

          {altura !== "plegado" && altura !== "vistazo" && (
            <>
              {/* en alerta o emergencia, a dónde acudir va primero */}
              {fuerte && acudir}
              {principal && (zona.caudal || principal.rio) && (
                <MedidorCaudal c={zona.caudal} rio={principal.rio} viejo={p.desactualizado} />
              )}
              <BarrasLluvia
                origen={origen}
                porGps={zona?.porGps}
                ciudad={ciudad?.name}
                depto={depto}
                revisada={Boolean(p.lluviaActualizada)}
                hora={p.lluviaActualizada}
                vieja={p.lluviaDesactualizada}
              />
              {!fuerte && acudir}
              <FranjaPronostico pron={pron} fechaMapa={fechaMapa} />
              {conDia && dia && elegir && (
                <div className="px-4 pt-3 lg:hidden">
                  <Titulo>Día de los avisos y del pronóstico en el mapa</Titulo>
                  <DiaSelector valor={dia} onCambiar={(v) => elegir("avisos", v)} className="mt-1 shadow-none" />
                </div>
              )}
            </>
          )}

          {altura === "completa" && (
            <>
              <div className="space-y-1.5 px-4 pt-4 text-sm text-muted-foreground">
                <Titulo>Qué dicen las fuentes hoy</Titulo>
                <p className="text-foreground">{p.local}</p>
                {zona?.resumenBd && !zona.titular.interpretado && (
                  <p className="text-foreground">
                    {zona.resumenBd.titular}{" "}
                    <span className="text-xs text-muted-foreground">
                      (resumen {zona.resumenBd.origen === "llm" ? "redactado automáticamente con las cifras oficiales" : "del servidor de SIMPAC"})
                    </span>
                  </p>
                )}
                {(p.avisos ?? []).map((a) => (
                  <p key={a} className="text-nivel-alerta">
                    {a}
                  </p>
                ))}
                {avisosZona.map((a) => (
                  <p key={a.referencia} className="flex gap-1.5 text-foreground">
                    <Megaphone className="mt-0.5 h-4 w-4 shrink-0" style={{ color: NIVEL_HEX[a.nivel] }} />
                    <span>
                      <span className="font-semibold">Aviso {COLOR_AVISO[a.nivel]} (según SENAMHI):</span> {a.detalle}.{" "}
                      <a href={URL_AVISO(a.referencia)} target="_blank" rel="noopener noreferrer" className="whitespace-nowrap text-xs text-muted-foreground underline">
                        Ver el aviso oficial
                      </a>
                    </span>
                  </p>
                ))}
                {riosConSenales.map(({ rio, estado }) => {
                  const f = fraseCorta(rio, estado);
                  return (
                    <p key={rio.id} className="flex gap-1.5 text-foreground">
                      <Waves className="mt-0.5 h-4 w-4 shrink-0" style={{ color: ZONA_HEX[estado.nivel] }} />
                      <span>
                        <span className="font-semibold">{f.texto}</span>
                        {f.accion ? ` ${f.accion}` : ""} {botonVer(rio)}
                      </span>
                    </p>
                  );
                })}
                {/* lluvia medida sobre la referencia: no es un aviso oficial, no lleva enlace a uno */}
                {lluviaZona.slice(0, 3).map((a) => (
                  <p key={a.referencia} className="flex gap-1.5 text-foreground">
                    <Droplets className="mt-0.5 h-4 w-4 shrink-0" style={{ color: NIVEL_HEX.aviso }} />
                    <span>
                      <span className="font-semibold">Lluvia medida:</span> {a.detalle}
                    </span>
                  </p>
                ))}
                {masLluvia > 0 && (
                  <p className="pl-[22px] text-foreground">
                    {masLluvia === 1
                      ? `Y 1 estación más en ${depto} pasó la referencia de SENAMHI.`
                      : `Y ${masLluvia} estaciones más en ${depto} pasaron la referencia de SENAMHI.`}
                  </p>
                )}
                {p.pais && <p>{p.pais}</p>}
                {p.lluvia && (
                  <p className="flex gap-1.5">
                    <Droplets className="mt-0.5 h-4 w-4 shrink-0 text-met" />
                    <span>{p.lluvia.frase}</span>
                  </p>
                )}
              </div>

              {/* El Niño: contexto de meses, no de hoy (en escritorio ya está en la barra lateral) */}
              <div className="px-4 pt-3">
                <button
                  type="button"
                  onClick={onElNino}
                  className="flex w-full items-center gap-2.5 rounded-xl border border-border bg-card px-3 py-2 text-left hover:bg-accent"
                >
                  <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full text-white" style={{ background: ENFEN_HEX[p.enfen?.corto] ?? "#9CA3AF" }}>
                    <ShieldAlert className="h-4 w-4" />
                  </span>
                  <span className="min-w-0 flex-1 leading-tight">
                    <span className="block text-[0.62rem] uppercase tracking-wider text-muted-foreground">{p.enfen?.quien ?? "El Niño costero"} (ENFEN)</span>
                    <span className="font-semibold">{p.enfen?.corto ?? "Sin dato"}</span>
                    {p.mar && <span className="block text-xs text-muted-foreground">Mar frente a la costa norte: {p.mar.corto}</span>}
                  </span>
                  <span className="text-xs text-muted-foreground">Ver gráficos</span>
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                </button>
              </div>

              <button
                type="button"
                onClick={() => setAbierto((a) => !a)}
                className="flex w-full items-center gap-1.5 px-4 pb-2 pt-3 text-left text-xs font-medium text-muted-foreground hover:text-foreground"
                aria-expanded={abierto}
              >
                {abierto ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                Qué significa esto
              </button>
              {abierto && (
                <div className="space-y-2.5 px-4 pb-3">
                  {p.enfen && (
                    <Explica titulo={p.enfen.titulo + "."} pie={p.enfen.fuente} aviso={p.enfen.atrasado ? "Puede haber un comunicado más nuevo." : null}>
                      {p.enfen.explica} {p.enfen.accion}
                    </Explica>
                  )}
                  {p.mar && (
                    <Explica titulo="Mar frente a la costa norte:" pie={p.mar.detalle} aviso={p.mar.atrasado}>
                      {p.mar.frase} Un mar más caliente suele traer lluvias fuertes a la costa norte y a las partes altas que miran
                      al mar (como el oeste de Cajamarca), sobre todo de diciembre a abril.
                    </Explica>
                  )}
                  {p.pacifico && (
                    <Explica titulo={p.pacifico.frase} pie={p.pacifico.detalle}>
                      Es el índice mundial de El Niño; para las lluvias del norte del Perú pesa más el mar frente a nuestra costa.
                    </Explica>
                  )}
                  <p className="text-xs text-muted-foreground">
                    Las alertas de ríos usan los niveles de ANA. Los avisos (amarillo, naranja y rojo) vienen de SENAMHI, y SIMPAC
                    los resume en palabras simples: el aviso oficial es el que publica SENAMHI. “Atentos a la lluvia” es otra cosa:
                    una estación automática de SENAMHI midió más lluvia que la referencia que SENAMHI usa para ese lugar, en la
                    última hora o sumando las últimas 6 horas. Esa referencia cambia de un lugar a otro: es baja donde casi no
                    llueve (1 mm en una hora en partes de la costa) y alta en la selva (hasta 25 mm). No es un aviso oficial, es la
                    lectura de una sola estación (que puede fallar) y en temporada de lluvias puede pasar varias veces. Ante una
                    emergencia, sigue las indicaciones de SENAMHI, INDECI y Defensa Civil.
                  </p>
                  <p className="text-xs text-muted-foreground">
                    En el mapa, un círculo con borde amarillo, naranja o rojo marca una zona con aviso de SENAMHI: la gota quiere
                    decir que puede llover en algún momento dentro de esa zona, no en toda ni todo el día. Los círculos blancos son
                    el pronóstico de SENAMHI para cada localidad (hoy, mañana y pasado); con borde punteado, SENAMHI escribe
                    «tendencia a»: es posible, no seguro. Las manchas azules con borde punteado son el nowcasting de SENAMHI: una
                    estimación experimental de las próximas 2 horas, no un aviso.
                  </p>
                  {rios.length > 0 && (
                    <p className="text-xs text-muted-foreground">
                      Las franjas junto al río Mashcón marcan la zona que podría inundarse si el río se desborda. Las rayadas son
                      una estimación de SIMPAC hecha con el relieve; las lisas vienen del estudio de INDECI de 2005 para la ciudad;
                      ninguna es un mapa oficial vigente. Se pintan de ámbar cuando hay señales en la cuenca (lluvia fuerte medida,
                      aviso naranja o rojo de SENAMHI por lluvias, el río cerca de su nivel de alerta o un aviso hidrológico
                      amarillo), de naranja o rojo solo cuando ANA mide el río sobre su nivel de alerta o de emergencia o SENAMHI
                      emite un aviso hidrológico naranja o rojo, y de azul cuando no hay señales (siguen siendo zonas que podrían
                      inundarse). Los rombos con un año son desbordes y daños pasados documentados.
                    </p>
                  )}
                  <p className="text-xs text-muted-foreground">
                    El medidor del río compara la última lectura de ANA con los niveles de alerta y emergencia que ANA publica para
                    esa estación; “cerca” (80 % del caudal de alerta) es un criterio de SIMPAC. Las distancias al río y a la zona
                    son en línea recta desde tu ubicación o desde el centro de la ciudad elegida.
                  </p>
                </div>
              )}

              {/* Reportar dentro de la hoja (desde lg es el botón flotante) */}
              <div className="px-4 pb-3 lg:hidden">
                <Button variant="destructive" className="w-full" onClick={onReportar}>
                  <Plus className="h-[18px] w-[18px]" />
                  Reportar incidente
                </Button>
              </div>

              <Button
                variant="ghost"
                disabled={!alertasCargadas || total === 0}
                onClick={onVerAlertas}
                className={cn("h-auto w-full justify-start gap-2 rounded-none border-t border-border py-3", `tz-${nivel}`, "tz-tinta")}
              >
                <TriangleAlert className="h-4 w-4" />
                {!alertasCargadas ? "Alertas: sin datos todavía" : total === 0 ? "No hay alertas ahora" : `Ver alertas (${total})`}
                {alertasCargadas && total > 0 && <ChevronRight className="ml-auto h-4 w-4" />}
              </Button>
            </>
          )}
        </div>

        {/* Fuentes: una línea en vistazo y media (plegada ya va la fuente y la hora de cada dato en la
            tarjeta); la leyenda literal que exigen los términos de SENAMHI en la altura completa (y en
            el panel de capas) */}
        {altura !== "plegado" && (
          <p className="shrink-0 border-t border-border px-4 py-1.5 text-[0.6rem] leading-snug text-muted-foreground">
            {altura === "completa" ? (
              <>Fuentes: SENAMHI, ANA, ENFEN, IGP, NOAA y NASA. {ATRIBUCION_SENAMHI}</>
            ) : (
              <>
                Fuentes: SENAMHI, ANA, ENFEN ·{" "}
                <button type="button" onClick={() => cambiar("completa", { mano: true })} className="underline hover:text-foreground">
                  ver atribución
                </button>
              </>
            )}
          </p>
        )}
      </div>
    </div>
  );
}
