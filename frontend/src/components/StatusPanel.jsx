import { useState } from "react";
import { ChevronDown, ChevronRight, ChevronUp, Droplets, Megaphone, Plus, ShieldAlert, TriangleAlert, Waves } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { NIVEL } from "@/lib/nivel";
import { ENFEN_HEX, NIVEL_HEX } from "@/map/palette";
import { horaPeru } from "@/lib/tiempo";
import { ATRIBUCION_SENAMHI } from "@/map/senamhi";

const COLOR_AVISO = { aviso: "amarillo", alerta: "naranja", emergencia: "rojo" };
const URL_AVISO = (referencia) =>
  referencia === "SENAMHI lluvia 24h"
    ? "https://www.senamhi.gob.pe/?p=aviso-24H"
    : "https://www.senamhi.gob.pe/?p=aviso-meteorologico";

function Metric({ Icon, color, value, label, title }) {
  return (
    <div
      title={title}
      className="flex min-w-0 flex-1 flex-col gap-1.5 rounded-xl border border-border bg-card p-2.5 sm:flex-row sm:items-center sm:gap-3 sm:p-3.5"
    >
      <div
        className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-white sm:h-9 sm:w-9"
        style={{ background: color }}
      >
        <Icon className="h-4 w-4 sm:h-[18px] sm:w-[18px]" />
      </div>
      <div className="min-w-0 leading-tight">
        <div className="break-words text-sm font-semibold sm:text-base">{value}</div>
        <div className="line-clamp-2 text-[0.68rem] text-muted-foreground sm:text-[0.72rem]">{label}</div>
      </div>
    </div>
  );
}

function Explica({ titulo, children, pie, aviso }) {
  return (
    <div className="text-sm leading-snug">
      <span className="font-semibold">{titulo}</span> {children}
      {aviso && <span className="block text-xs text-nivel-alerta">{aviso}</span>}
      {pie && <span className="block text-xs text-muted-foreground">{pie}</span>}
    </div>
  );
}

export default function StatusPanel({
  depto,
  porGps,
  local,
  pais,
  nivelLocal = "normal",
  etiqueta,
  cuantasAqui = 0,
  cuantasFuera = 0,
  cuantasTotal = 0,
  enfen,
  mar,
  pacifico,
  lluvia,
  avisos = [],
  avisosZona = [],
  lluviaZona = [],
  nivelOficialAqui = "normal",
  alertasCargadas = true,
  actualizado,
  desactualizado,
  lluviaActualizada,
  lluviaDesactualizada,
}) {
  const [abierto, setAbierto] = useState(false);
  // plegado deja solo el titular: en pantallas chicas el panel tapa el mapa y sus capas
  const [plegado, setPlegado] = useState(false);
  const nv = NIVEL[nivelLocal];
  const total = cuantasTotal;
  // estaciones de la zona que pasaron la referencia de SENAMHI: las 3 primeras con su detalle
  const masLluvia = lluviaZona.length - 3;

  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-0 z-[600] p-3 md:p-4">
      <div className="pointer-events-auto mx-auto max-h-[70vh] max-w-3xl overflow-y-auto rounded-2xl border border-border bg-card/95 shadow-2xl backdrop-blur">
        <div className={cn("h-1 w-full", nv.strip)} />
        <div className="flex items-start gap-3 px-4 pt-3.5">
          <div className="min-w-0">
            <div className="text-[0.68rem] uppercase tracking-wider text-muted-foreground">
              Estado · {depto}
              {porGps && <span className="normal-case tracking-normal"> (tu ubicación)</span>}
              {actualizado && (
                <span className={cn("ml-1 normal-case tracking-normal", desactualizado && "text-nivel-alerta")}>
                  · ríos: {desactualizado ? "sin actualizar desde" : "actualizado"} {horaPeru(actualizado)}
                </span>
              )}
              {lluviaActualizada && (
                <span className={cn("ml-1 normal-case tracking-normal", lluviaDesactualizada && "text-nivel-alerta")}>
                  · lluvia: {lluviaDesactualizada ? "sin actualizar desde" : "actualizada"} {horaPeru(lluviaActualizada)}
                </span>
              )}
            </div>
            <h3 className="text-base font-semibold leading-snug md:text-lg">{local}</h3>
          </div>
          <div className="ml-auto flex shrink-0 items-center gap-1">
            <Badge variant="outline" className={cn("gap-1.5", nv.border, nv.text)}>
              <TriangleAlert className="h-3.5 w-3.5" />
              {etiqueta ?? nv.label}
            </Badge>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={() => setPlegado((p) => !p)}
              aria-expanded={!plegado}
              aria-label={plegado ? "Mostrar el detalle" : "Plegar el panel"}
            >
              {plegado ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </Button>
          </div>
        </div>

        {plegado ? (
          <div className="pb-2" />
        ) : (
          <>
            <div className="space-y-1 px-4 pt-1 text-sm text-muted-foreground">
              {avisos.map((a) => (
                <p key={a} className="text-nivel-alerta">
                  {a}
                </p>
              ))}
              {avisosZona.map((a) => (
                <p key={a.referencia} className="flex gap-1.5 text-foreground">
                  <Megaphone className="mt-0.5 h-4 w-4 shrink-0" style={{ color: NIVEL_HEX[a.nivel] }} />
                  <span>
                    <span className="font-semibold">Aviso {COLOR_AVISO[a.nivel]} (según SENAMHI):</span> {a.detalle}.{" "}
                    <a
                      href={URL_AVISO(a.referencia)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="whitespace-nowrap text-xs text-muted-foreground underline"
                    >
                      Ver el aviso oficial
                    </a>
                  </span>
                </p>
              ))}
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
              {pais && <p>{pais}</p>}
              {lluvia && (
                <p className="flex gap-1.5">
                  <Droplets className="mt-0.5 h-4 w-4 shrink-0 text-met" />
                  <span>{lluvia.frase}</span>
                </p>
              )}
            </div>

            <div className="grid grid-cols-3 gap-2 px-4 py-3 sm:flex">
              <Metric
                Icon={ShieldAlert}
                color={ENFEN_HEX[enfen?.corto] ?? "#9CA3AF"}
                value={enfen?.corto ?? "Sin dato"}
                label={enfen ? `${enfen.quien} (ENFEN)` : "Sistema de alerta ENFEN"}
                title={enfen ? `${enfen.explica} ${enfen.fuente}` : undefined}
              />
              <Metric
                Icon={Waves}
                color="#3B3BEB"
                value={mar?.corto ?? "Sin dato"}
                label="Mar frente a la costa norte"
                title={mar ? `${mar.frase} ${mar.detalle}` : undefined}
              />
              <Metric
                Icon={TriangleAlert}
                color={NIVEL_HEX[nivelOficialAqui] ?? "#9CA3AF"}
                value={alertasCargadas ? cuantasAqui : "Sin dato"}
                label={alertasCargadas ? `alertas y avisos en ${depto} · ${cuantasFuera} en el resto del país` : "alertas"}
              />
            </div>

            <button
              type="button"
              onClick={() => setAbierto((a) => !a)}
              className="flex w-full items-center gap-1.5 px-4 pb-2 text-left text-xs font-medium text-muted-foreground hover:text-foreground"
              aria-expanded={abierto}
            >
              {abierto ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
              Qué significa esto
            </button>
            {abierto && (
              <div className="space-y-2.5 px-4 pb-3">
                {enfen && (
                  <Explica titulo={enfen.titulo + "."} pie={enfen.fuente} aviso={enfen.atrasado ? "Puede haber un comunicado más nuevo." : null}>
                    {enfen.explica} {enfen.accion}
                  </Explica>
                )}
                {mar && (
                  <Explica titulo="Mar frente a la costa norte:" pie={mar.detalle} aviso={mar.atrasado}>
                    {mar.frase} Un mar más caliente suele traer lluvias fuertes a la costa norte y a las partes altas
                    que miran al mar (como el oeste de Cajamarca), sobre todo de diciembre a abril.
                  </Explica>
                )}
                {pacifico && (
                  <Explica titulo={pacifico.frase} pie={pacifico.detalle}>
                    Es el índice mundial de El Niño; para las lluvias del norte del Perú pesa más el mar frente a nuestra costa.
                  </Explica>
                )}
                <p className="text-xs text-muted-foreground">
                  Las alertas de ríos usan los niveles de ANA. Los avisos (amarillo, naranja y rojo) vienen de
                  SENAMHI, y SIMPAC los resume en palabras simples: el aviso oficial es el que publica SENAMHI.
                  “Atentos a la lluvia” es otra cosa: una estación automática de SENAMHI midió más lluvia que la
                  referencia que SENAMHI usa para ese lugar, en la última hora o sumando las últimas 6 horas. Esa
                  referencia cambia de un lugar a otro: es baja donde casi no llueve (1 mm en una hora en partes de
                  la costa) y alta en la selva (hasta 25 mm). No es un aviso oficial, es la lectura de una sola
                  estación (que puede fallar) y en temporada de lluvias puede pasar varias veces. Ante una
                  emergencia, sigue las indicaciones de SENAMHI, INDECI y Defensa Civil.
                </p>
              </div>
            )}

            {/* Reportar dentro del panel (en pantallas anchas es el botón flotante) */}
            <div className="px-4 pb-3 2xl:hidden">
              <Button variant="destructive" className="w-full">
                <Plus className="h-[18px] w-[18px]" />
                Reportar incidente
              </Button>
            </div>

            <Button
              variant="ghost"
              disabled={!alertasCargadas || total === 0}
              className={cn("h-auto w-full justify-start gap-2 rounded-none border-t border-border py-3", nv.text)}
            >
              <TriangleAlert className="h-4 w-4" />
              {!alertasCargadas ? "Alertas: sin datos todavía" : total === 0 ? "No hay alertas ahora" : `Ver alertas (${total})`}
              {alertasCargadas && total > 0 && <ChevronRight className="ml-auto h-4 w-4" />}
            </Button>
          </>
        )}

        {/* Fuentes y la leyenda literal que exigen los términos de SENAMHI, siempre a la vista */}
        <p className="border-t border-border px-4 py-1.5 text-[0.6rem] leading-snug text-muted-foreground">
          Fuentes: SENAMHI, ANA, ENFEN, IGP, NOAA y NASA. {ATRIBUCION_SENAMHI}
        </p>
      </div>
    </div>
  );
}
