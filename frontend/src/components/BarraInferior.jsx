import { NavLink } from "react-router-dom";
import { Map, MessageSquare, TriangleAlert, User, Users } from "lucide-react";
import { cn } from "@/lib/utils";
import { useSesion } from "@/hooks/useSesion";

const PESTANAS = [
  { to: "/", label: "Mapa", Icon: Map, end: true },
  { to: "/alertas", label: "Alertas", Icon: TriangleAlert, badge: true },
  { to: "/comunidad", label: "Comunidad", Icon: Users },
  { to: "/chat", label: "Chat", Icon: MessageSquare },
  { to: "/cuenta", label: "Cuenta", Icon: User },
];

// Barra de navegación de 5 pestañas para pantallas más angostas que md (donde no hay barra
// lateral): 56 px de alto, debajo del mapa (no lo tapa ni tapa el panel de estado), con el
// contador de alertas y, con sesión, el nombre de la persona en la pestaña Cuenta.
export default function BarraInferior({ alertCount = 0 }) {
  const { conSesion, nombre } = useSesion();
  return (
    <nav
      aria-label="Secciones"
      className="flex h-14 flex-none items-stretch border-t border-border bg-background pb-[env(safe-area-inset-bottom)] md:hidden"
    >
      {PESTANAS.map(({ to, label, Icon, end, badge }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) =>
            cn(
              "relative flex flex-1 flex-col items-center justify-center gap-0.5 text-[0.64rem] font-medium leading-none",
              isActive ? "text-foreground" : "text-muted-foreground"
            )
          }
        >
          {({ isActive }) => (
            <>
              <span className={cn("grid h-7 w-12 place-items-center rounded-full", isActive && "bg-primary text-primary-foreground")}>
                <Icon className="h-[18px] w-[18px]" />
              </span>
              <span className="max-w-[4.5rem] truncate">{to === "/cuenta" && conSesion && nombre ? nombre : label}</span>
              {badge && alertCount > 0 && (
                <span className="absolute left-1/2 top-1 ml-2 min-w-[1.1rem] rounded-full bg-destructive px-1 text-center text-[0.6rem] font-bold leading-4 text-destructive-foreground">
                  {alertCount}
                </span>
              )}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}
