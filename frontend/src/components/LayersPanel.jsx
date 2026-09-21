import { Radio, Waves, TriangleAlert, ShieldAlert, Droplets } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";

const LAYERS = [
  { id: "est", label: "Estaciones", Icon: Radio },
  { id: "rio", label: "Ríos", Icon: Waves },
  { id: "inc", label: "Incidentes", Icon: TriangleAlert },
  { id: "zona", label: "Zonas de riesgo", Icon: ShieldAlert },
  { id: "anom", label: "Anomalías de lluvia", Icon: Droplets },
];

const LEGEND = [
  { color: "#DB0404", label: "Río en emergencia" },
  { color: "#F58E27", label: "Río en alerta" },
  { color: "#F58E27", label: "Lluvia bajo lo normal" },
  { color: "#3BA5EB", label: "Lluvia sobre lo normal" },
];

export default function LayersPanel({ visible, onToggle }) {
  return (
    <div className="absolute right-[70px] top-4 z-[601] w-60 rounded-xl border border-border bg-popover/95 p-4 shadow-2xl backdrop-blur">
      <h4 className="mb-3 text-[0.68rem] font-semibold uppercase tracking-widest text-muted-foreground">
        Capas del mapa
      </h4>
      <div className="flex flex-col gap-0.5">
        {LAYERS.map(({ id, label, Icon }) => (
          <label
            key={id}
            className="flex cursor-pointer items-center gap-3 rounded-md px-1.5 py-1.5 text-sm hover:bg-accent"
          >
            <Icon className="h-[18px] w-[18px] text-muted-foreground" />
            <span>{label}</span>
            <Switch
              className="ml-auto"
              checked={visible[id]}
              onCheckedChange={() => onToggle(id)}
            />
          </label>
        ))}
      </div>
      <Separator className="my-3" />
      <div className="flex flex-col gap-2">
        {LEGEND.map(({ color, label }) => (
          <div
            key={label}
            className="flex items-center gap-2.5 text-xs text-muted-foreground"
          >
            <span
              className="h-3 w-3 rounded-full"
              style={{ background: color }}
            />
            {label}
          </div>
        ))}
      </div>
    </div>
  );
}
