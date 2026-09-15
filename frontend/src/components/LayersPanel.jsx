import { IcStation, IcRiver, IcAlerta, IcUsers, IcZone } from "../icons.jsx";

const LAYERS = [
  { id: "est", label: "Estaciones", Icon: IcStation },
  { id: "rio", label: "Ríos", Icon: IcRiver },
  { id: "inc", label: "Incidentes", Icon: IcAlerta },
  { id: "usr", label: "Usuarios cercanos", Icon: IcUsers },
  { id: "zona", label: "Zonas de riesgo", Icon: IcZone },
];

export default function LayersPanel({ visible, onToggle }) {
  return (
    <div className="layers">
      <h4>Capas del mapa</h4>
      {LAYERS.map(({ id, label, Icon }) => (
        <label className="lrow" key={id}>
          <Icon size={18} /> {label}
          <span className="sw">
            <input type="checkbox" checked={visible[id]} onChange={() => onToggle(id)} />
            <i />
          </span>
        </label>
      ))}
      <div className="legend">
        <span><span className="c" style={{ background: "var(--n-emerg)" }} /> Zona inundación</span>
        <span><span className="c" style={{ background: "var(--n-alerta)" }} /> Zona alerta</span>
        <span><span className="c" style={{ background: "var(--inc-lluvia)" }} /> Lluvia activa</span>
      </div>
    </div>
  );
}
