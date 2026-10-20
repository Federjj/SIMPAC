import { Link } from "react-router-dom";
import { CircleAlert, Inbox, Loader2, LogIn } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { POR_QUE_CUENTA } from "@/lib/comunidad";

// Estados comunes de las páginas: cargando, vacío, error (con reintento) y "entra para...".

export function Cargando({ texto = "Cargando…", className }) {
  return (
    <p role="status" className={cn("flex items-center gap-2 py-6 text-sm text-muted-foreground", className)}>
      <Loader2 className="h-4 w-4 animate-spin" />
      {texto}
    </p>
  );
}

export function Vacio({ titulo, texto, children, className }) {
  return (
    <div className={cn("rounded-xl border border-dashed border-border px-4 py-6 text-center", className)}>
      <Inbox className="mx-auto mb-2 h-6 w-6 text-muted-foreground" />
      <p className="text-sm font-semibold">{titulo}</p>
      {texto && <p className="mt-1 text-sm text-muted-foreground">{texto}</p>}
      {children}
    </div>
  );
}

export function ErrorCarga({ texto = "No se pudo cargar. Revisa tu conexión.", onReintentar, className }) {
  return (
    <div role="alert" className={cn("flex flex-wrap items-center gap-3 rounded-xl border border-nivel-alerta/50 bg-nivel-alerta/10 px-4 py-3 text-sm", className)}>
      <CircleAlert className="h-4 w-4 shrink-0 text-nivel-alerta" />
      <span className="min-w-0 flex-1">{texto}</span>
      {onReintentar && (
        <Button variant="outline" size="sm" onClick={onReintentar}>
          Reintentar
        </Button>
      )}
    </div>
  );
}

// Bloque "Entra para ..." de las rutas protegidas: el contenido público se ve igual; esto solo
// invita a entrar. `que`: "reportar", "votar", "comentar", "chatear".
export function EntraPara({ que, className, compacto = false }) {
  return (
    <div className={cn("rounded-xl border border-border bg-muted/40 px-4 py-3 text-sm", className)}>
      <p className="font-semibold">Entra para {que}.</p>
      {!compacto && <p className="mt-0.5 text-muted-foreground">{POR_QUE_CUENTA}</p>}
      <Button asChild size="sm" className="mt-2">
        <Link to="/cuenta">
          <LogIn className="h-4 w-4" />
          Iniciar sesión o crear cuenta
        </Link>
      </Button>
    </div>
  );
}

// Mensaje corto de resultado bajo un formulario (ok o error).
export function Mensaje({ tipo = "error", children, className }) {
  if (!children) return null;
  return (
    <p
      role={tipo === "error" ? "alert" : "status"}
      className={cn(
        "rounded-lg px-3 py-2 text-sm",
        tipo === "error" ? "bg-nivel-emergencia/10 text-nivel-emergencia" : "bg-nivel-normal/15 text-green-800",
        className
      )}
    >
      {children}
    </p>
  );
}
