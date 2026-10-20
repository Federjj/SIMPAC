import { useState } from "react";
import { Link } from "react-router-dom";
import { ThumbsDown, ThumbsUp } from "lucide-react";
import { cn } from "@/lib/utils";
import { useSesion } from "@/hooks/useSesion";
import { getReporte, votar } from "@/lib/queries";
import { mensajeErrorBD, vigente } from "@/lib/comunidad";

// Botones "a favor" / "en contra" de un reporte con sus contadores. Con sesión votan (upsert en
// voto; tocar el mismo voto lo quita); sin sesión invitan a entrar. Los contadores los recalcula
// la BD: tras votar se vuelve a pedir el reporte y se avisa con onCambio(reporte, miVoto).
export default function Votos({ reporte, miVoto = null, onCambio, className }) {
  const { conSesion } = useSesion();
  const [enviando, setEnviando] = useState(false);
  const [aviso, setAviso] = useState(null);
  const vencido = !vigente(reporte);

  const tocar = async (valor) => {
    if (!conSesion) {
      setAviso("entrar");
      return;
    }
    if (vencido) {
      setAviso("Este reporte ya venció: no admite votos.");
      return;
    }
    setEnviando(true);
    setAviso(null);
    const nuevo = miVoto === valor ? null : valor;
    const { error } = await votar(reporte.id, nuevo);
    if (error) {
      setAviso(mensajeErrorBD(error, "votar"));
    } else {
      const fresco = await getReporte(reporte.id).catch(() => null);
      onCambio?.(fresco ?? reporte, nuevo);
    }
    setEnviando(false);
  };

  const boton = (valor, Icon, n, etiqueta) => {
    const activo = miVoto === valor;
    return (
      <button
        type="button"
        onClick={() => tocar(valor)}
        disabled={enviando}
        aria-pressed={activo}
        aria-label={`${etiqueta}: ${n}`}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-sm font-semibold transition-colors disabled:opacity-60",
          activo
            ? valor === 1
              ? "border-green-700 bg-green-700 text-white"
              : "border-nivel-emergencia bg-nivel-emergencia text-white"
            : "border-border bg-card hover:bg-accent"
        )}
      >
        <Icon className="h-4 w-4" />
        {n}
      </button>
    );
  };

  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
      {boton(1, ThumbsUp, reporte.likes ?? 0, "A favor")}
      {boton(-1, ThumbsDown, reporte.dislikes ?? 0, "En contra")}
      {aviso === "entrar" ? (
        <span className="text-xs text-muted-foreground">
          <Link to="/cuenta" className="font-medium underline">
            Entra
          </Link>{" "}
          para votar.
        </span>
      ) : aviso ? (
        <span role="alert" className="text-xs text-nivel-emergencia">
          {aviso}
        </span>
      ) : null}
    </div>
  );
}
