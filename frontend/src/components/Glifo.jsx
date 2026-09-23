import { cn } from "@/lib/utils";
import { glifoSvg } from "@/map/iconos";

// Glifo del tiempo (map/iconos.js: constantes, nunca datos) para la franja, las leyendas y el
// panel. El tamaño lo da className (h-9 w-9...).
export default function Glifo({ nombre, className }) {
  return (
    <span
      className={cn("glifo inline-block", className)}
      aria-hidden="true"
      dangerouslySetInnerHTML={{ __html: glifoSvg(nombre) }}
    />
  );
}
