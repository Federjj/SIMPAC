import { Thermometer, Waves, TriangleAlert, ChevronRight, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { NIVEL } from "@/lib/nivel";
import { NIVEL_HEX } from "@/map/palette";
import { horaPeru } from "@/lib/tiempo";

const fmt = (v) => (v == null ? "—" : (v >= 0 ? "+" : "") + v);

function Metric({ Icon, color, value, label }) {
  return (
    <div className="flex flex-1 flex-col gap-1.5 rounded-xl border border-border bg-card p-2.5 sm:flex-row sm:items-center sm:gap-3 sm:p-3.5">
      <div
        className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-white sm:h-9 sm:w-9"
        style={{ background: color }}
      >
        <Icon className="h-4 w-4 sm:h-[18px] sm:w-[18px]" />
      </div>
      <div className="min-w-0 leading-tight">
        <div className="text-base font-semibold tabular-nums sm:text-lg">{value}</div>
        <div className="truncate text-[0.68rem] text-muted-foreground sm:text-[0.72rem]">{label}</div>
      </div>
    </div>
  );
}

export default function StatusPanel({
  titular,
  nivel = "normal",
  alertCount = 0,
  oni,
  icen,
  actualizado,
  desactualizado,
}) {
  const nv = NIVEL[nivel];
  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-0 z-[600] p-3 md:p-4">
      <div className="pointer-events-auto mx-auto max-w-3xl overflow-hidden rounded-2xl border border-border bg-card/95 shadow-2xl backdrop-blur">
        <div className={cn("h-1 w-full", nv.strip)} />
        <div className="flex items-start gap-3 px-4 pt-3.5">
          <div className="min-w-0">
            <div className="text-[0.68rem] uppercase tracking-wider text-muted-foreground">
              Estado · Perú
              {actualizado && (
                <span className={cn("ml-1 normal-case tracking-normal", desactualizado && "text-nivel-alerta")}>
                  · {desactualizado ? "sin actualizar desde" : "actualizado"} {horaPeru(actualizado)}
                </span>
              )}
            </div>
            <h3 className="truncate text-base font-semibold md:text-lg">
              {titular}
            </h3>
          </div>
          <Badge
            variant="outline"
            className={cn("ml-auto shrink-0 gap-1.5", nv.border, nv.text)}
          >
            <TriangleAlert className="h-3.5 w-3.5" />
            {nv.label}
          </Badge>
        </div>

        <div className="grid grid-cols-3 gap-2 px-4 py-3 sm:flex">
          <Metric Icon={Thermometer} color="#3BA5EB" value={fmt(oni?.valor)} label={`ONI · ${oni?.categoria || "El Niño"}`} />
          <Metric Icon={Waves} color="#3B3BEB" value={fmt(icen?.valor)} label={`ICEN · ${icen?.categoria || "costero"}`} />
          <Metric Icon={TriangleAlert} color={NIVEL_HEX[nivel]} value={alertCount} label="alertas vigentes" />
        </div>

        {/* Reportar dentro del panel (solo movil; en desktop es el boton flotante) */}
        <div className="px-4 pb-3 sm:hidden">
          <Button variant="destructive" className="w-full">
            <Plus className="h-[18px] w-[18px]" />
            Reportar incidente
          </Button>
        </div>

        <Button
          variant="ghost"
          className={cn("h-auto w-full justify-start gap-2 rounded-none border-t border-border py-3", nv.text)}
        >
          <TriangleAlert className="h-4 w-4" />
          Ver alertas vigentes ({alertCount})
          <ChevronRight className="ml-auto h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
