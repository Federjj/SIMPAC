import { TriangleAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { NIVEL } from "@/lib/nivel";
import { cn } from "@/lib/utils";

// Semáforo con color y etiqueta (nunca solo color): `nivel` de NIVEL (normal, aviso, alerta,
// emergencia, sin_dato) y una `etiqueta` opcional ("Aviso naranja", "Atentos a la lluvia").
export default function NivelBadge({ nivel = "sin_dato", etiqueta, className }) {
  const nv = NIVEL[nivel] ?? NIVEL.sin_dato;
  return (
    <Badge variant="outline" className={cn("gap-1.5 whitespace-nowrap", nv.border, nv.text, nv.softbg, className)}>
      <TriangleAlert className="h-3.5 w-3.5" />
      {etiqueta ?? nv.label}
    </Badge>
  );
}
