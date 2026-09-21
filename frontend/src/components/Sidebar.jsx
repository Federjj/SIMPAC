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

const NAV = [
  { id: "mapa", label: "Mapa", Icon: Map },
  { id: "alertas", label: "Alertas", Icon: TriangleAlert, badgeKey: "alertCount" },
  { id: "comunidad", label: "Comunidad", Icon: Users },
  { id: "chat", label: "Chat", Icon: MessageSquare },
  { id: "cuenta", label: "Cuenta", Icon: User },
];

const fmt = (v) => (v == null ? "—" : (v >= 0 ? "+" : "") + v);

export default function Sidebar({ active = "mapa", nivel = "normal", alertCount = 0, oni, icen }) {
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
              Monitoreo · Cajamarca
            </div>
          </div>
        </div>
      </div>

      {/* Estado actual (real) */}
      <div className={cn("mx-4 mb-3 rounded-xl border px-4 py-3 flex items-center gap-3", nv.border, nv.softbg)}>
        <span className={cn("h-2.5 w-2.5 rotate-45 rounded-[2px]", nv.dot)} />
        <div className="leading-tight">
          <div className="text-[0.68rem] uppercase tracking-wider text-muted-foreground">
            Estado actual
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

      {/* Pie: contexto El Niño (datos reales) */}
      <div className="mt-auto border-t border-border p-4">
        <div className="mb-3 flex items-center gap-2 text-[0.68rem] uppercase tracking-widest text-muted-foreground">
          <Radio className={cn("h-3.5 w-3.5 animate-pulse", nv.text)} />
          Datos en vivo
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-lg border border-border bg-card px-3 py-2">
            <div className="text-lg font-semibold tabular-nums">{fmt(oni?.valor)}</div>
            <div className="text-[0.66rem] font-semibold text-met">ONI</div>
            <div className="truncate text-[0.66rem] text-muted-foreground">{oni?.categoria || "El Niño"}</div>
          </div>
          <div className="rounded-lg border border-border bg-card px-3 py-2">
            <div className="text-lg font-semibold tabular-nums">{fmt(icen?.valor)}</div>
            <div className="text-[0.66rem] font-semibold text-hid">ICEN</div>
            <div className="truncate text-[0.66rem] text-muted-foreground">{icen?.categoria || "El Niño costero"}</div>
          </div>
        </div>
        <p className="my-3 text-xs text-muted-foreground">
          Referencial · Emergencias:{" "}
          <span className="font-semibold text-nivel-alerta">105 / 116</span>
        </p>
        <Button className="w-full">
          <LogIn className="h-4 w-4" />
          Iniciar sesión
        </Button>
      </div>
    </aside>
  );
}
