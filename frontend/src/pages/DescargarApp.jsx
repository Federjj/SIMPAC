import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bell, Check, Copy, Download, ExternalLink, MapPin, Smartphone, TriangleAlert } from "lucide-react";
import PanelPagina from "@/components/PanelPagina";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// Enlace estable a la última publicación de la app en GitHub: cada release lleva el archivo
// `SIMPAC.apk` adjunto y GitHub redirige a la versión más nueva. Sin `download` (es otro dominio:
// el navegador lo ignoraría) y sin `target=_blank` (la descarga no necesita otra pestaña).
export const URL_APK = "https://github.com/Federjj/SIMPAC/releases/latest/download/SIMPAC.apk";
export const URL_REPO = "https://github.com/Federjj/SIMPAC";
export const TAMANO_APK = "unos 17 MB";
export const ANDROID_MINIMO = "Android 8 o más nuevo";

const PASOS = [
  "Toca \"Descargar para Android (APK)\" y espera a que termine la descarga (unos 17 MB).",
  "Abre el archivo SIMPAC.apk desde las notificaciones o desde la carpeta Descargas.",
  "Si el celular pregunta, permite que tu navegador instale apps de origen desconocido (solo esta vez).",
  "Toca Instalar y abre SIMPAC. Elige tu zona en Cuenta o deja que use tu ubicación.",
];

// Botón grande de descarga; lo usa esta página y la tarjeta de Cuenta.
export function BotonDescargarApk({ className }) {
  return (
    <Button asChild size="lg" className={cn("h-12 w-full text-base", className)}>
      <a href={URL_APK} rel="noopener">
        <Download className="h-5 w-5" />
        Descargar para Android (APK)
      </a>
    </Button>
  );
}

// "Copiar enlace": deja el enlace del APK en el portapapeles para pegarlo en WhatsApp. Si el
// navegador no deja copiar, muestra el enlace para seleccionarlo a mano.
function CopiarEnlace() {
  const [estado, setEstado] = useState("listo"); // listo | copiado | manual
  useEffect(() => {
    if (estado !== "copiado") return undefined;
    const t = setTimeout(() => setEstado("listo"), 2500);
    return () => clearTimeout(t);
  }, [estado]);
  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(URL_APK);
      setEstado("copiado");
    } catch {
      setEstado("manual");
    }
  };
  return (
    <div>
      <Button type="button" variant="outline" className="w-full" onClick={copiar} aria-live="polite">
        {estado === "copiado" ? <Check className="h-4 w-4 text-green-700" /> : <Copy className="h-4 w-4" />}
        {estado === "copiado" ? "Enlace copiado" : "Copiar enlace"}
      </Button>
      <p className="mt-1.5 text-xs text-muted-foreground">Pégalo en WhatsApp para compartirlo con tu familia o tus vecinos.</p>
      {estado === "manual" && (
        <p className="mt-1 break-all rounded-md bg-muted px-2 py-1 text-xs" role="status">
          No se pudo copiar solo. Selecciona y copia este enlace: {URL_APK}
        </p>
      )}
    </div>
  );
}

function Punto({ Icon, children }) {
  return (
    <li className="flex items-start gap-2">
      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
      <span>{children}</span>
    </li>
  );
}

// Página /app: qué es la app Android, el botón de descarga del APK, requisitos, pasos de
// instalación, el aviso de que no está en Play Store y la nota de privacidad. No consulta nada en
// vivo: si todavía no hay una publicación en GitHub, el enlace responde 404 pero la página se ve igual.
export default function DescargarApp() {
  return (
    <PanelPagina titulo="SIMPAC en tu celular" subtitulo="App Android nativa, gratis">
      <div className="space-y-5 text-sm">
        <section className="rounded-xl border border-border bg-card p-4">
          <div className="flex items-start gap-3">
            <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-primary text-primary-foreground">
              <Smartphone className="h-6 w-6" />
            </span>
            <div>
              <h2 className="text-base font-semibold">La misma información, en una app</h2>
              <p className="mt-1 text-muted-foreground">
                SIMPAC para Android es una app nativa con el mapa, las alertas de tu zona y a dónde acudir en una
                emergencia. Lo que agrega frente a la web: te avisa con una notificación cuando tu departamento entra en
                alerta o emergencia oficial, aunque tengas la app cerrada.
              </p>
            </div>
          </div>
          <ul className="mt-3 space-y-1.5">
            <Punto Icon={MapPin}>El mapa con los ríos, los avisos de SENAMHI, las estaciones y los lugares a dónde acudir.</Punto>
            <Punto Icon={TriangleAlert}>Las alertas vigentes de tu zona, con el semáforo y el titular en lenguaje claro.</Punto>
            <Punto Icon={Bell}>Notificaciones opcionales solo por alerta o emergencia oficial; nunca por un aviso amarillo.</Punto>
          </ul>
          <div className="mt-4">
            <BotonDescargarApk />
            <p className="mt-2 text-center text-xs text-muted-foreground">
              Archivo SIMPAC.apk, {TAMANO_APK} · {ANDROID_MINIMO} · descarga desde GitHub
            </p>
          </div>
        </section>

        <section>
          <h2 className="text-sm font-semibold">Cómo instalarla</h2>
          <ol className="mt-2 space-y-2">
            {PASOS.map((paso, i) => (
              <li key={paso} className="flex items-start gap-3">
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-muted text-xs font-semibold">{i + 1}</span>
                <span>{paso}</span>
              </li>
            ))}
          </ol>
        </section>

        <section className="rounded-xl border border-nivel-alerta/50 bg-nivel-alerta/10 px-4 py-3">
          <h2 className="text-sm font-semibold">Todavía no está en Play Store</h2>
          <p className="mt-1 text-muted-foreground">
            Por eso se instala desde este archivo y Android avisa que viene de "origen desconocido": es normal. La
            versión que descargas la firma el equipo del proyecto SIMPAC y es la última publicada en GitHub. Si el
            enlace no abre, la publicación todavía no está lista: vuelve a intentar más tarde.
          </p>
        </section>

        <section>
          <h2 className="text-sm font-semibold">Tu privacidad</h2>
          <p className="mt-1 text-muted-foreground">
            La app solo pide tu ubicación para mostrar tu zona y los lugares cercanos a dónde acudir; puedes negarla y
            elegir tu ciudad a mano. Las notificaciones son opcionales: se prenden y se apagan en la pestaña Cuenta de la
            app. Hoy la app solo declara tres permisos: internet, ubicación y notificaciones.
          </p>
        </section>

        <section className="space-y-3">
          <CopiarEnlace />
          <Button asChild variant="ghost" className="w-full">
            <a href={URL_REPO} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="h-4 w-4" />
              Ver el código en GitHub
            </a>
          </Button>
          <p className="text-xs text-muted-foreground">
            Requisitos: {ANDROID_MINIMO} y conexión a internet. La web sigue funcionando igual en el celular:
            <Link to="/" className="ml-1 underline">
              volver al mapa
            </Link>
            .
          </p>
        </section>
      </div>
    </PanelPagina>
  );
}
