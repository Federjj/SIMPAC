import { useEffect, useRef, useState } from "react";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import { GRUPOS } from "@/map/layers";
import { ATRIBUCION_SENAMHI } from "@/map/senamhi";

// Muestra de color de la leyenda: punto (marcadores), anillo (borde de un marcador),
// gota (reportes) o cuadro translúcido (áreas sombreadas).
function Muestra({ color, zona, gota, anillo }) {
  return (
    <span
      className={cn(
        "h-3 w-3 shrink-0",
        gota ? "-rotate-45 rounded-[50%_50%_50%_0]" : zona ? "rounded-[3px]" : "rounded-full",
        zona && "border"
      )}
      style={
        anillo
          ? { background: "transparent", border: `2px solid ${color}` }
          : zona
            ? { background: `${color}66`, borderColor: color }
            : { background: color }
      }
    />
  );
}

function Capa({ layer, on, opcion, nota, destacada, onToggle, onOpcion }) {
  const { id, label, Icon, legend = [], opciones, fuente } = layer;
  const leyenda = typeof legend === "function" ? legend(opcion ?? opciones?.defecto) : legend;
  const ref = useRef(null);
  const [anillo, setAnillo] = useState(false);
  // la capa que se acaba de prender desde otro lado (p. ej. el panel El Niño) se trae a la vista
  // y se marca un momento; `destacada` es un contador (0 = no)
  useEffect(() => {
    if (!destacada) return;
    ref.current?.scrollIntoView({ block: "start", behavior: "smooth" });
    setAnillo(true);
    const t = setTimeout(() => setAnillo(false), 2500);
    return () => clearTimeout(t);
  }, [destacada]);
  return (
    <div ref={ref} className={cn("rounded-md transition-shadow", anillo && "ring-1 ring-primary/40")}>
      <label className="flex cursor-pointer items-center gap-3 rounded-md px-1.5 py-1.5 text-sm hover:bg-accent">
        <Icon className="h-[18px] w-[18px] shrink-0 text-muted-foreground" />
        <span className="leading-tight">{label}</span>
        <Switch className="ml-auto shrink-0" checked={on} onCheckedChange={() => onToggle(id)} />
      </label>
      {on && (
        <div className="mb-2 ml-9 mt-0.5 flex flex-col gap-1.5">
          {opciones && (
            <select
              value={opcion ?? opciones.defecto}
              onChange={(e) => onOpcion(id, e.target.value)}
              className="w-full rounded-md border border-border bg-background px-2 py-1 text-xs"
              aria-label={opciones.etiqueta}
            >
              {opciones.valores.map((v) => (
                <option key={v.valor} value={v.valor}>
                  {v.etiqueta}
                </option>
              ))}
            </select>
          )}
          {nota && <div className="text-xs text-foreground">{nota}</div>}
          {leyenda.map((item) => (
            <div key={item.label} className="flex items-center gap-2 text-xs text-muted-foreground">
              <Muestra {...item} />
              {item.label}
            </div>
          ))}
          {fuente && <div className="text-[0.66rem] leading-snug text-muted-foreground">{fuente}</div>}
        </div>
      )}
    </div>
  );
}

export default function LayersPanel({ layers, visible, opciones = {}, notas = {}, destacar, onToggle, onOpcion }) {
  return (
    <div className="absolute right-[70px] top-4 z-[601] max-h-[calc(100%-2rem)] w-72 overflow-y-auto rounded-xl border border-border bg-popover/95 p-4 shadow-2xl backdrop-blur">
      <h4 className="mb-2 text-[0.68rem] font-semibold uppercase tracking-widest text-muted-foreground">
        Capas del mapa
      </h4>
      {GRUPOS.map((grupo) => {
        const deGrupo = layers.filter((l) => l.grupo === grupo);
        if (!deGrupo.length) return null;
        return (
          <div key={grupo} className="mb-2">
            <div className="mb-0.5 mt-2 text-[0.66rem] font-semibold uppercase tracking-wider text-muted-foreground/80">
              {grupo}
            </div>
            {deGrupo.map((layer) => (
              <Capa
                key={layer.id}
                layer={layer}
                on={Boolean(visible[layer.id])}
                opcion={opciones[layer.id]}
                nota={notas[layer.id]}
                destacada={destacar?.id === layer.id ? destacar.vez : 0}
                onToggle={onToggle}
                onOpcion={onOpcion}
              />
            ))}
          </div>
        );
      })}
      <p className="mt-3 border-t border-border pt-2 text-[0.62rem] leading-snug text-muted-foreground">
        Ríos: ANA. Lluvia, avisos y mapas: SENAMHI. {ATRIBUCION_SENAMHI} Lluvia por satélite: NASA. El Niño: ENFEN,
        IGP y NOAA.
      </p>
    </div>
  );
}
