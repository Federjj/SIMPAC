import {
  Map,
  TriangleAlert,
  Users,
  MessageSquare,
  User,
  LogIn,
  Radio,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { NIVEL } from "@/lib/nivel";
import { horaPeru, horasDesde } from "@/lib/tiempo";

const NAV = [
  { id: "mapa", label: "Mapa", Icon: Map },
  { id: "alertas", label: "Alertas", Icon: TriangleAlert, badgeKey: "alertCount" },
  { id: "comunidad", label: "Comunidad", Icon: Users },
  { id: "chat", label: "Chat", Icon: MessageSquare },
  { id: "cuenta", label: "Cuenta", Icon: User },
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
  active = "mapa",
  depto,
  nivel = "normal",
  alertCount = 0,
  enfen,
  mar,
  pacifico,
  actualizado,
  desactualizado,
  sinConexion,
}) {
  const nv = NIVEL[nivel];
  return (
    <aside className="hidden md:flex w-72 flex-none flex-col h-screen border-r border-border bg-background">
      {/* Marca */}
      <div className="px-5 pt-5 pb-4">
        <div className="flex items-center gap-2">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-primary text-primary-foreground font-bold">
            S
          </div>
          <div>
            <div className="text-lg font-bold leading-none tracking-tight">
              SIM<span className="text-primary">PAC</span>
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              Ríos, lluvia y El Niño · Perú
            </div>
          </div>
        </div>
      </div>

      {/* Estado en la zona del usuario */}
      <div className={cn("mx-4 mb-3 rounded-xl border px-4 py-3 flex items-center gap-3", nv.border, nv.softbg)}>
        <span className={cn("h-2.5 w-2.5 rotate-45 rounded-[2px]", nv.dot)} />
        <div className="leading-tight">
          <div className="text-[0.68rem] uppercase tracking-wider text-muted-foreground">
            Estado en {depto}
          </div>
          <div className={cn("text-sm font-semibold", nv.text)}>{nv.label}</div>
        </div>
      </div>

      {/* Navegacion */}
      <nav className="px-3 flex flex-col gap-1">
        {NAV.map(({ id, label, Icon, badgeKey }) => {
          const badge = badgeKey === "alertCount" ? alertCount : 0;
          return (
            <a
              key={id}
              href="#"
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                id === active
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground"
              )}
            >
              <Icon className="h-[18px] w-[18px] shrink-0" />
              <span>{label}</span>
              {badge > 0 ? (
                <Badge
                  variant="destructive"
                  className="ml-auto h-5 min-w-5 justify-center rounded-full px-1.5"
                >
                  {badge}
                </Badge>
              ) : null}
            </a>
          );
        })}
      </nav>

      {/* Pie: contexto El Niño en palabras (datos reales) */}
      <div className="mt-auto border-t border-border p-4">
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
          <Contexto titulo="Mar frente al Perú" valor={mar?.corto} detalle={mar?.detalle} aviso={mar?.atrasado} />
          <Contexto titulo="Pacífico central" valor={pacifico?.corto} detalle={pacifico?.detalle} />
        </div>
        <p className="my-3 text-xs text-muted-foreground">
          Emergencias: <span className="font-semibold text-nivel-alerta">105 (Policía) · 116 (Bomberos)</span>
        </p>
        <Button className="w-full">
          <LogIn className="h-4 w-4" />
          Iniciar sesión
        </Button>
      </div>
    </aside>
  );
}
