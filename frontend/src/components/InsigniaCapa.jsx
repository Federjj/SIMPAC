import { cn } from "@/lib/utils";

// "Oficial" (dato de SENAMHI tal cual) o "Experimental" (producto en calibración), junto al
// nombre de una capa o en el chip del nowcasting.
const CLASES = {
  Oficial: "border-sky-200 bg-sky-50 text-sky-800",
  Experimental: "border-dashed border-slate-400 text-slate-600",
};

export default function InsigniaCapa({ tipo, className }) {
  if (!CLASES[tipo]) return null;
  return (
    <span
      className={cn(
        "ml-1 rounded border px-1 text-[0.55rem] font-semibold uppercase tracking-wider",
        CLASES[tipo],
        className
      )}
    >
      {tipo}
    </span>
  );
}
