import { Ban, Car, CircleDot, CloudRain, Droplets, Info, Mountain, TriangleAlert } from "lucide-react";
import { REPORT_TYPE } from "@/lib/reportTypes";
import { cn } from "@/lib/utils";

// Ícono lucide de cada tipo de reporte (los pines del mapa usan los SVG de map/markers.js con la
// misma idea), sobre el color del tipo.
export const ICONO_TIPO = {
  inundacion: Droplets,
  huayco: Mountain,
  lluvia_intensa: CloudRain,
  via_bloqueada: Ban,
  atasco: Car,
  bache: CircleDot,
  accidente: TriangleAlert,
  otro: Info,
};

export default function IconoReporte({ tipo, className, tamano = "md" }) {
  const t = REPORT_TYPE[tipo] ?? REPORT_TYPE.otro;
  const Icon = ICONO_TIPO[t.id] ?? Info;
  return (
    <span
      aria-hidden="true"
      className={cn(
        "grid shrink-0 place-items-center rounded-full text-white",
        tamano === "sm" ? "h-7 w-7" : tamano === "lg" ? "h-12 w-12" : "h-9 w-9",
        className
      )}
      style={{ background: t.color }}
    >
      <Icon className={tamano === "sm" ? "h-4 w-4" : tamano === "lg" ? "h-6 w-6" : "h-5 w-5"} />
    </span>
  );
}
