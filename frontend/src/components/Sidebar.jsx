import { Link, NavLink } from "react-router-dom";
import {
  Map,
  TriangleAlert,
  Users,
  MessageSquare,
  User,
  LogIn,
  Radio,
  BarChart3,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import TelefonoCopiable from "@/components/TelefonoCopiable";
import { cn } from "@/lib/utils";
import { NIVEL } from "@/lib/nivel";
import { horaPeru, horasDesde } from "@/lib/tiempo";
import { useSesion } from "@/hooks/useSesion";

export const SUBTITULO_SIFEC = "Sistema Inteligente de Acceso a Información del Fenómeno El Niño";

const NAV = [
  { to: "/", label: "Mapa", Icon: Map, end: true },
  { to: "/alertas", label: "Alertas", Icon: TriangleAlert, badgeKey: "alertCount" },
  { to: "/comunidad", label: "Comunidad", Icon: Users },
  { to: "/chat", label: "Chat", Icon: MessageSquare },
  { to: "/cuenta", label: "Cuenta", Icon: User },
];

// Una línea del contexto El Niño: la palabra primero, el número y la fuente en chico.
function Contexto({ titulo, valor, detalle, aviso }) {
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 leading-tight">
      <div className="text-[0.66rem] text-muted-foreground">{titulo}</div>
      <div className="text-sm font-semibold">{valor ?? "Sin dato"}</div>
      {detalle && <div className="mt-0.5 text-[0.66rem] text-muted-foreground">{detalle}</div>}
      {aviso && <div className="mt-0.5 text-[0.66rem] text-nivel-alerta">{aviso}</div>}
    </div>
  );
}

export default function Sidebar({
  depto,
  nivel = "normal",
  etiqueta,
  alertCount = 0,
  enfen,
  mar,
  pacifico,
  actualizado,
  desactualizado,
  sinConexion,
  onElNino,
}) {
  const nv = NIVEL[nivel];
  const { conSesion, nombre, cargando } = useSesion();
  return (
    <aside className="hidden md:flex w-72 flex-none flex-col h-screen overflow-hidden border-r border-border bg-background">
      {/* Marca */}
      <div className="px-5 pt-5 pb-4">
        <div className="flex items-center gap-2">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-primary text-primary-foreground font-bold">
            S
          </div>
          <div>
            <div className="text-lg font-bold leading-none tracking-tight">
              SI<span className="text-primary">FEC</span>
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              Ríos, lluvia y El Niño - Perú
            </div>
          </div>
        </div>
        <p className="mt-2 text-[0.62rem] leading-snug text-muted-foreground">{SUBTITULO_SIFEC}</p>
      </div>

      {/* Navegacion */}
      <nav className="px-3 flex flex-col gap-1" aria-label="Secciones">
        {NAV.map(({ to, label, Icon, badgeKey, end }) => {
          const badge = badgeKey === "alertCount" ? alertCount : 0;
          return (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground"
                )
              }
            >
              <Icon className="h-[18px] w-[18px] shrink-0" />
              <span>{to === "/cuenta" && conSesion && nombre ? nombre : label}</span>
              {badge > 0 ? (
                <Badge
                  variant="destructive"
                  className="ml-auto h-5 min-w-5 justify-center rounded-full px-1.5"
                >
                  {badge}
                </Badge>
              ) : null}
            </NavLink>
          );
        })}
      </nav>

      {/* Pie: contexto El Niño en palabras (datos reales) */}
      <div className="mt-auto min-h-0 overflow-y-auto overscroll-contain border-t border-border p-4">
        <div className="mb-3 flex items-center gap-2 text-[0.68rem] uppercase tracking-widest text-muted-foreground">
          {sinConexion ? (
            <>
              <Radio className="h-3.5 w-3.5 text-nivel-alerta" />
              <span className="text-nivel-alerta">Sin conexión con los datos</span>
            </>
          ) : !actualizado ? (
            <>
              <Radio className="h-3.5 w-3.5" />
              Consultando datos…
            </>
          ) : desactualizado ? (
            <>
              <Radio className="h-3.5 w-3.5 text-nivel-alerta" />
              <span className="text-nivel-alerta">Sin actualizar hace {horasDesde(actualizado)} h</span>
            </>
          ) : (
            <>
              <Radio className={cn("h-3.5 w-3.5 animate-pulse", nv.text)} />
              Datos en vivo{actualizado ? ` · ${horaPeru(actualizado)}` : ""}
            </>
          )}
        </div>
        <div className="flex flex-col gap-2">
          <Contexto
            titulo={enfen ? `${enfen.quien} (ENFEN)` : "Sistema de alerta ENFEN"}
            valor={enfen?.corto}
            detalle={enfen?.fuente}
            aviso={enfen?.atrasado ? "Puede haber un comunicado más nuevo." : null}
          />
          <Contexto titulo="Mar frente a la costa norte" valor={mar?.corto} detalle={mar?.detalle} aviso={mar?.atrasado} />
          <Contexto titulo="Pacífico central" valor={pacifico?.corto} detalle={pacifico?.detalle} />
          <Button variant="outline" size="sm" className="w-full" onClick={onElNino}>
            <BarChart3 className="h-4 w-4" />
            Ver El Niño en gráficos
          </Button>
        </div>
        <p className="my-3 text-xs text-muted-foreground">
          Emergencias:{" "}
          <span className="font-semibold text-nivel-alerta">
            <TelefonoCopiable numero="105" /> (Policía) · <TelefonoCopiable numero="116" /> (Bomberos)
          </span>
        </p>
        {conSesion ? (
          <Button asChild variant="outline" className="w-full">
            <Link to="/cuenta">
              <User className="h-4 w-4" />
              <span className="truncate">{nombre ?? "Mi cuenta"}</span>
            </Link>
          </Button>
        ) : (
          <Button asChild className="w-full" disabled={cargando}>
            <Link to="/cuenta">
              <LogIn className="h-4 w-4" />
              Iniciar sesión
            </Link>
          </Button>
        )}
      </div>
    </aside>
  );
}
