import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

// Copia un texto al portapapeles (con respaldo para navegadores sin la API o sin https).
export async function copiarTexto(texto) {
  try {
    await navigator.clipboard.writeText(texto);
    return true;
  } catch {
    try {
      const ta = document.createElement("textarea");
      ta.value = texto;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      ta.remove();
      return ok;
    } catch {
      return false;
    }
  }
}

// Número de teléfono como texto: al tocarlo se copia (no abre la app de llamadas) y por un
// momento dice "Copiado".
export default function TelefonoCopiable({ numero, className, titulo, children }) {
  const [copiado, setCopiado] = useState(false);
  const t = useRef(null);
  useEffect(() => () => clearTimeout(t.current), []);
  const copiar = async () => {
    const limpio = String(numero).replace(/[^\d+]/g, "") || String(numero);
    if (await copiarTexto(limpio)) {
      setCopiado(true);
      clearTimeout(t.current);
      t.current = setTimeout(() => setCopiado(false), 1800);
    }
  };
  return (
    <button
      type="button"
      onClick={copiar}
      title={titulo ?? "Tocar para copiar el número"}
      aria-label={`Copiar el número ${numero}`}
      className={cn("cursor-copy underline decoration-dotted underline-offset-2 hover:text-foreground", className)}
    >
      {copiado ? "Copiado" : (children ?? numero)}
    </button>
  );
}
