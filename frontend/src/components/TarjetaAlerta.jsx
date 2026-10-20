import { ExternalLink } from "lucide-react";
import NivelBadge from "@/components/NivelBadge";
import { etiquetaAlerta, fuenteAlerta, nivelDe, textoZonas, tituloAlerta } from "@/lib/alertas";
import { horaPeru } from "@/lib/tiempo";
import { cn } from "@/lib/utils";

// Una alerta de la vista alerta_actual (o de la tabla alerta, ya agrupada por lib/alertas.js):
// nivel con color y etiqueta, referencia, zona, detalle en lenguaje claro, hora, fuente y enlace.
// La lluvia medida se marca siempre como no oficial.
export default function TarjetaAlerta({ a, className }) {
  const nivel = nivelDe(a);
  const fuente = fuenteAlerta(a);
  const zonas = textoZonas(a.zonas ?? (a.zona ? [a.zona] : []));
  const num = (v) => Number(v).toLocaleString("es-PE", { maximumFractionDigits: 1 });
  return (
    <article className={cn("rounded-xl border border-border bg-card p-3.5", className)}>
      <div className="flex flex-wrap items-center gap-2">
        <NivelBadge nivel={nivel} etiqueta={etiquetaAlerta(a)} />
        {!fuente.oficial && (
          <span className="rounded border border-dashed border-muted-foreground/60 px-1.5 text-[0.62rem] font-semibold uppercase tracking-wider text-muted-foreground">
            No oficial
          </span>
        )}
        {a.vigente === false && <span className="text-[0.68rem] text-muted-foreground">ya no está vigente</span>}
        <span className="ml-auto text-xs text-muted-foreground">{a.ts ? horaPeru(a.ts) : ""}</span>
      </div>
      <h3 className="mt-2 text-sm font-semibold leading-snug">{tituloAlerta(a)}</h3>
      {zonas && <p className="text-xs text-muted-foreground">{zonas}</p>}
      {a.detalle && <p className="mt-1.5 text-sm leading-snug">{a.detalle}</p>}
      {a.tipo === "lluvia" && a.valor != null && a.umbral != null && (
        <p className="mt-1 text-xs text-muted-foreground">
          Midió {num(a.valor)} mm en {a.ventana_h === 6 ? "6 horas" : "1 hora"}; la referencia de SENAMHI para esa estación es {num(a.umbral)} mm.
          Es la lectura de una sola estación, no un aviso oficial.
        </p>
      )}
      <p className="mt-2 flex flex-wrap items-center gap-x-2 text-[0.7rem] text-muted-foreground">
        <span>Fuente: {fuente.nombre}</span>
        {fuente.url && (
          <a href={fuente.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 underline hover:text-foreground">
            {fuente.oficial ? "Ver la fuente oficial" : "Ver en SENAMHI"}
            <ExternalLink className="h-3 w-3" />
          </a>
        )}
      </p>
    </article>
  );
}
