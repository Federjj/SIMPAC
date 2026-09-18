import { CloudRain, Waves, Thermometer, TriangleAlert, ChevronRight, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

function Metric({ Icon, color, value, label }) {
  return (
    <div className="flex flex-1 flex-col gap-1.5 rounded-xl border border-border bg-card p-2.5 sm:flex-row sm:items-center sm:gap-3 sm:p-3.5">
      <div
        className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-white sm:h-9 sm:w-9"
        style={{ background: color }}
      >
        <Icon className="h-4 w-4 sm:h-[18px] sm:w-[18px]" />
      </div>
      <div className="leading-tight">
        <div className="text-base font-semibold tabular-nums sm:text-lg">{value}</div>
        <div className="text-[0.68rem] text-muted-foreground sm:text-[0.72rem]">{label}</div>
      </div>
    </div>
  );
}

export default function StatusPanel({ titular, metrics }) {
  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-0 z-[600] p-3 md:p-4">
      <div className="pointer-events-auto mx-auto max-w-3xl overflow-hidden rounded-2xl border border-border bg-card/95 shadow-2xl backdrop-blur">
        <div className="h-1 w-full bg-nivel-alerta" />
        <div className="flex items-start gap-3 px-4 pt-3.5">
          <div className="min-w-0">
            <div className="text-[0.68rem] uppercase tracking-wider text-muted-foreground">
              Estado · 09:30
            </div>
            <h3 className="truncate text-base font-semibold md:text-lg">
              {titular}
            </h3>
          </div>
          <Badge
            variant="outline"
            className="ml-auto shrink-0 gap-1.5 border-nivel-alerta/50 text-nivel-alerta"
          >
            <TriangleAlert className="h-3.5 w-3.5" />
            Alerta
          </Badge>
        </div>

        <div className="grid grid-cols-3 gap-2 px-4 py-3 sm:flex">
          <Metric Icon={CloudRain} color="#3BA5EB" value={metrics.lluvia} label="mm/hr Lluvia" />
          <Metric Icon={Waves} color="#3B3BEB" value={metrics.rio} label="m³/s Río" />
          <Metric Icon={Thermometer} color="#F58E27" value={metrics.temp} label="Temperatura" />
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
          className="h-auto w-full justify-start gap-2 rounded-none border-t border-border py-3 text-nivel-alerta hover:text-nivel-alerta"
        >
          <TriangleAlert className="h-4 w-4" />
          Ver alertas vigentes (3)
          <ChevronRight className="ml-auto h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
