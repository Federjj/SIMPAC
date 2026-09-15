import { IcMapa, IcAlerta, IcComunidad, IcChat, IcCuenta, IcLogin } from "../icons.jsx";

const NAV = [
  { id: "mapa", label: "Mapa", Icon: IcMapa },
  { id: "alertas", label: "Alertas", Icon: IcAlerta, badge: 3 },
  { id: "comunidad", label: "Comunidad", Icon: IcComunidad },
  { id: "chat", label: "Chat", Icon: IcChat },
  { id: "cuenta", label: "Cuenta", Icon: IcCuenta },
];

export default function Sidebar({ active = "mapa", metrics }) {
  return (
    <aside className="side">
      <div className="brand">
        <div className="logo">SIM<b>PAC</b></div>
        <div className="sub">Monitoreo · Cajamarca</div>
      </div>

      <div className="estado">
        <span className="dot" />
        <div>
          <div className="lab">Estado actual</div>
          <div className="val">Alerta</div>
        </div>
      </div>

      <nav>
        {NAV.map(({ id, label, Icon, badge }) => (
          <a key={id} href="#" className={id === active ? "active" : ""}>
            <Icon /> {label}
            {badge ? <span className="badge">{badge}</span> : null}
          </a>
        ))}
      </nav>

      <div className="foot">
        <div className="live"><span className="pulse" /> En vivo · 09:30</div>
        <div className="metrics">
          <div className="metric"><b>{metrics.lluvia}</b><div className="u">mm/hr</div><div className="t">Lluvia</div></div>
          <div className="metric"><b>{metrics.rio}</b><div className="u">m³/s</div><div className="t">Río</div></div>
        </div>
        <div className="emerg">Referencial · Emergencias: <b>105 / 116</b></div>
        <button className="btn-login"><IcLogin size={15} /> Iniciar sesión</button>
      </div>
    </aside>
  );
}
