import { cn } from "@/lib/utils";
import InsigniaCapa from "@/components/InsigniaCapa";

const OTRO_DIA = "El nowcasting es solo para las próximas 2 horas: elige Hoy.";

// Chip del nowcasting (con la capa encendida): qué muestra y de cuándo es, con un punto azul
// que late si el dato está fresco y gris si está viejo o falló. Al tocarlo abre el panel de capas.
// `nota` es la que devuelve layers/nowcast.js ({texto, corto, estado}); un texto suelto es de
// MapView ("Cargando…" o "No se pudo cargar…").
export default function ChipNowcast({ nota, dia = "ahora", onAbrir, className }) {
  const otroDia = dia !== "ahora";
  const obj = nota && typeof nota === "object" ? nota : null;
  const estado = otroDia
    ? "otro"
    : obj
      ? obj.estado
      : typeof nota === "string" && nota.startsWith("No se pudo")
        ? "error"
        : "cargando";
  const texto = otroDia
    ? OTRO_DIA
    : obj
      ? obj.corto
      : estado === "error"
        ? "No se pudo consultar el nowcasting"
        : "Consultando el nowcasting de SENAMHI…";
  const fresco = estado === "fresco" || estado === "vacio";
  return (
    <button
      type="button"
      onClick={onAbrir}
      title={obj && !otroDia ? obj.texto : texto}
      className={cn(
        "flex max-w-full items-center gap-2 rounded-full border border-border bg-card/90 py-1.5 pl-3 pr-2 text-xs font-medium shadow-lg backdrop-blur hover:bg-accent",
        className
      )}
    >
      <span
        className={cn(
          "h-2 w-2 shrink-0 rounded-full",
          fresco ? "animate-pulse bg-[#3B3BEB] motion-reduce:animate-none" : "bg-slate-400"
        )}
      />
      <span className={cn("min-w-0 truncate", !fresco && "text-muted-foreground")}>{texto}</span>
      <InsigniaCapa tipo="Experimental" className="ml-0 shrink-0" />
    </button>
  );
}
