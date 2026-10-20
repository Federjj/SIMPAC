import { Link } from "react-router-dom";
import { ChevronRight, MapPin } from "lucide-react";
import IconoReporte from "@/components/IconoReporte";
import Votos from "@/components/Votos";
import { ESTADO_REPORTE, hace, nombreReporte, textoDistancia, venceEn } from "@/lib/comunidad";
import { cn } from "@/lib/utils";

// Tarjeta de un reporte ciudadano: tipo con ícono, descripción, foto, hace cuánto, distancia
// (si se conoce), estado según la comunidad, votos y "Ver en el mapa". `detalle` = versión
// grande para la página del reporte (sin el enlace al detalle).
export default function TarjetaReporte({ r, miVoto, onCambio, onVerMapa, detalle = false, className }) {
  const descartado = r.estado === "descartado";
  return (
    <article className={cn("rounded-xl border border-border bg-card p-3.5", descartado && "opacity-75", className)}>
      <div className="flex items-start gap-3">
        <IconoReporte tipo={r.tipo} tamano={detalle ? "lg" : "md"} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-2">
            <h3 className={cn("font-semibold leading-snug", detalle ? "text-lg" : "text-sm")}>{nombreReporte(r)}</h3>
            <span className="text-xs text-muted-foreground">{hace(r.creado_en)}</span>
            {r.distanciaKm != null && <span className="text-xs text-muted-foreground">· {textoDistancia(r.distanciaKm)}</span>}
          </div>
          <p className="text-[0.7rem] text-muted-foreground">
            {ESTADO_REPORTE[r.estado] ?? "Sin confirmar"} · {venceEn(r.expira_en)}
          </p>
          {r.descripcion && (
            <p className={cn("mt-1.5 whitespace-pre-line text-sm leading-snug", !detalle && "line-clamp-3")}>{r.descripcion}</p>
          )}
        </div>
      </div>
      {r.foto_url && (
        <a href={r.foto_url} target="_blank" rel="noopener noreferrer" className="mt-3 block">
          <img
            src={r.foto_url}
            alt={`Foto del reporte: ${nombreReporte(r)}`}
            loading="lazy"
            className={cn("w-full rounded-lg object-cover", detalle ? "max-h-96" : "max-h-48")}
          />
        </a>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Votos reporte={r} miVoto={miVoto} onCambio={onCambio} />
        <span className="ml-auto flex items-center gap-2">
          {onVerMapa && r.lat != null && (
            <button
              type="button"
              onClick={() => onVerMapa(r)}
              className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground underline hover:text-foreground"
            >
              <MapPin className="h-3.5 w-3.5" />
              Ver en el mapa
            </button>
          )}
          {!detalle && (
            <Link to={`/comunidad/${r.id}`} className="inline-flex items-center gap-0.5 text-xs font-medium underline hover:text-foreground">
              Detalle y comentarios
              <ChevronRight className="h-3.5 w-3.5" />
            </Link>
          )}
        </span>
      </div>
    </article>
  );
}
