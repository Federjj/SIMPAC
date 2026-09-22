import { useState } from "react";
import { ChevronDown, ChevronRight, Droplets, Plus, ShieldAlert, TriangleAlert, Waves } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { NIVEL } from "@/lib/nivel";
import { NIVEL_HEX } from "@/map/palette";
import { horaPeru } from "@/lib/tiempo";

// Color del estado ENFEN: alerta en naranja, vigilancia en amarillo, sin alerta en verde.
const ENFEN_HEX = { Alerta: NIVEL_HEX.alerta, Vigilancia: "#EBEB3B", "Sin alerta": NIVEL_HEX.normal };

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
  cuantasAqui = 0,
  cuantasFuera = 0,
  enfen,
  mar,
  pacifico,
  lluvia,
  avisos = [],
  alertasCargadas = true,
  actualizado,
  desactualizado,
}) {
  const [abierto, setAbierto] = useState(false);
  const nv = NIVEL[nivelLocal];
  const total = cuantasAqui + cuantasFuera;

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
                  · ríos y lluvia: {desactualizado ? "sin actualizar desde" : "actualizado"} {horaPeru(actualizado)}
                </span>
              )}
            </div>
            <h3 className="text-base font-semibold leading-snug md:text-lg">{local}</h3>
          </div>
          <Badge variant="outline" className={cn("ml-auto shrink-0 gap-1.5", nv.border, nv.text)}>
            <TriangleAlert className="h-3.5 w-3.5" />
            {nv.label}
          </Badge>
        </div>

        <div className="space-y-1 px-4 pt-1 text-sm text-muted-foreground">
          {avisos.map((a) => (
            <p key={a} className="text-nivel-alerta">
              {a}
            </p>
          ))}
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
            label="Mar frente al Perú"
            title={mar ? `${mar.frase} ${mar.detalle}` : undefined}
          />
          <Metric
            Icon={TriangleAlert}
            color={NIVEL_HEX[nivelLocal] ?? "#9CA3AF"}
            value={alertasCargadas ? cuantasAqui : "Sin dato"}
            label={alertasCargadas ? `alertas en ${depto} · ${cuantasFuera} en el resto del país` : "alertas"}
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
              <Explica titulo="Mar frente al Perú:" pie={mar.detalle} aviso={mar.atrasado}>
                {mar.frase} Un mar más caliente frente a la costa norte suele traer más lluvia a la costa y sierra norte, sobre todo de diciembre a abril.
              </Explica>
            )}
            {pacifico && (
              <Explica titulo={pacifico.frase} pie={pacifico.detalle}>
                Es el índice mundial de El Niño; para las lluvias del norte del Perú pesa más el mar frente a nuestra costa.
              </Explica>
            )}
            <p className="text-xs text-muted-foreground">
              Las alertas de ríos usan los niveles de ANA; las de lluvia son referenciales de SIMPAC. Ante
              una emergencia, sigue las indicaciones de SENAMHI, INDECI y Defensa Civil.
            </p>
          </div>
        )}

        {/* Reportar dentro del panel (solo móvil; en desktop es el botón flotante) */}
        <div className="px-4 pb-3 sm:hidden">
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
      </div>
    </div>
  );
}
