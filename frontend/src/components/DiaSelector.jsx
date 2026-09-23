import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { etiquetaDia, fechaDeOpcion } from "@/lib/pronostico";
import { diaCorto, fechaPeru } from "@/lib/tiempo";

const OPCIONES = ["ahora", "manana", "pasado"];

// Hoy / Mañana / (día de pasado mañana): mueve a la vez los avisos y el pronóstico del mapa
// (opción vinculada "dia" de las dos capas). Desde sm, la fecha corta debajo.
export default function DiaSelector({ valor = "ahora", onCambiar, className }) {
  const hoy = fechaPeru();
  return (
    <TooltipProvider delayDuration={500}>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            role="group"
            aria-label="Día de los avisos y del pronóstico"
            className={cn(
              "inline-flex gap-0.5 rounded-xl border border-border bg-card/95 p-[3px] shadow-lg backdrop-blur",
              className
            )}
          >
            {OPCIONES.map((o) => {
              const fecha = fechaDeOpcion(o);
              const activo = valor === o;
              return (
                <button
                  key={o}
                  type="button"
                  aria-pressed={activo}
                  onClick={() => onCambiar(o)}
                  className={cn(
                    "rounded-[9px] px-3 py-1.5 text-left text-[0.8rem] font-semibold leading-4 transition-colors sm:py-1",
                    activo ? "bg-foreground text-background" : "text-muted-foreground hover:bg-accent hover:text-foreground"
                  )}
                >
                  <span className="block">{etiquetaDia(fecha, hoy)}</span>
                  <span
                    className={cn(
                      "hidden text-[0.66rem] font-medium leading-3 sm:block",
                      activo ? "text-background/70" : "text-muted-foreground/80"
                    )}
                  >
                    {diaCorto(fecha)}
                  </span>
                </button>
              );
            })}
          </div>
        </TooltipTrigger>
        <TooltipContent side="bottom">Cambia el día de los avisos y del pronóstico en el mapa</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
