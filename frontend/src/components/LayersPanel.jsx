import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

// Muestra de color de la leyenda: punto (marcadores), gota (reportes) o
// círculo translúcido (zonas sombreadas).
function Muestra({ color, zona, gota }) {
  return (
    <span
      className={cn(
        "h-3 w-3 shrink-0",
        gota ? "-rotate-45 rounded-[50%_50%_50%_0]" : "rounded-full",
        zona && "border"
      )}
      style={zona ? { background: `${color}33`, borderColor: color } : { background: color }}
    />
  );
}

export default function LayersPanel({ layers, visible, onToggle }) {
  return (
    <div className="absolute right-[70px] top-4 z-[601] max-h-[calc(100%-2rem)] w-64 overflow-y-auto rounded-xl border border-border bg-popover/95 p-4 shadow-2xl backdrop-blur">
      <h4 className="mb-3 text-[0.68rem] font-semibold uppercase tracking-widest text-muted-foreground">
        Capas del mapa
      </h4>
      <div className="flex flex-col gap-0.5">
        {layers.map(({ id, label, Icon, legend = [] }) => (
          <div key={id}>
            <label className="flex cursor-pointer items-center gap-3 rounded-md px-1.5 py-1.5 text-sm hover:bg-accent">
              <Icon className="h-[18px] w-[18px] text-muted-foreground" />
              <span>{label}</span>
              <Switch className="ml-auto" checked={Boolean(visible[id])} onCheckedChange={() => onToggle(id)} />
            </label>
            {visible[id] && legend.length > 0 && (
              <div className="mb-2 ml-9 mt-0.5 flex flex-col gap-1.5">
                {legend.map((item) => (
                  <div key={item.label} className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Muestra {...item} />
                    {item.label}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
