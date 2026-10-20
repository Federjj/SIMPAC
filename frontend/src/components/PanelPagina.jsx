import { useEffect, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { DISCLAIMER } from "@/lib/comunidad";

// Marco de una página que se dibuja sobre el mapa: cabecera con el título (h1, recibe el foco al
// entrar, para los lectores de pantalla y el teclado), botón para volver, cuerpo con scroll y, si
// `disclaimer`, el texto legal al pie (Alertas, Comunidad y Chat). `volver` es la ruta del botón
// de atrás (por defecto, el mapa); `acciones` va a la derecha del título.
export default function PanelPagina({ titulo, subtitulo, volver = "/", acciones, disclaimer = false, pie, className, children }) {
  const h1 = useRef(null);
  const navigate = useNavigate();
  useEffect(() => {
    document.title = `${titulo} · SIMPAC`;
    h1.current?.focus({ preventScroll: true });
    return () => {
      document.title = "SIMPAC";
    };
  }, [titulo]);
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="flex items-start gap-2 border-b border-border px-4 pb-3 pt-3 md:px-5">
        {volver && (
          <Button variant="ghost" size="icon" className="-ml-2 h-9 w-9 shrink-0 lg:hidden" onClick={() => navigate(volver)} aria-label="Volver al mapa">
            <ArrowLeft className="h-5 w-5" />
          </Button>
        )}
        <div className="min-w-0 flex-1 pt-1">
          <h1 ref={h1} tabIndex={-1} className="text-lg font-bold leading-tight tracking-tight outline-none md:text-xl">
            {titulo}
          </h1>
          {subtitulo && <p className="mt-0.5 text-xs text-muted-foreground">{subtitulo}</p>}
        </div>
        {acciones}
        {volver && (
          <Button asChild variant="ghost" size="icon" className="hidden h-9 w-9 shrink-0 lg:inline-flex" aria-label="Cerrar y volver al mapa">
            <Link to={volver}>
              <X className="h-5 w-5" />
            </Link>
          </Button>
        )}
      </header>
      <div className={cn("min-h-0 flex-1 overflow-y-auto px-4 py-4 md:px-5", className)}>{children}</div>
      {(disclaimer || pie) && (
        <footer className="border-t border-border px-4 py-2 text-[0.68rem] leading-snug text-muted-foreground md:px-5">
          {pie}
          {disclaimer && <p>{DISCLAIMER}</p>}
        </footer>
      )}
    </div>
  );
}
