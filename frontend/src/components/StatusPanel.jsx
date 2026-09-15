import { IcAlerta, IcRain, IcRiver, IcTemp } from "../icons.jsx";

export default function StatusPanel({ titular, metrics }) {
  return (
    <div className="status">
      <div className="grip" />
      <div className="head">
        <div>
          <div className="k">Estado · 09:30</div>
          <h3>{titular}</h3>
        </div>
        <span className="tag"><IcAlerta size={14} /> Alerta</span>
      </div>
      <div className="cards">
        <div className="card">
          <div className="ic" style={{ background: "var(--met)" }}><IcRain size={18} /></div>
          <div><b>{metrics.lluvia}</b> <span className="t">mm/hr Lluvia</span></div>
        </div>
        <div className="card">
          <div className="ic" style={{ background: "var(--hid)" }}><IcRiver size={18} /></div>
          <div><b>{metrics.rio}</b> <span className="t">m³/s Río</span></div>
        </div>
        <div className="card">
          <div className="ic" style={{ background: "var(--n-aviso)" }}><IcTemp size={18} /></div>
          <div><b>{metrics.temp}</b> <span className="t">Temperatura</span></div>
        </div>
      </div>
      <div className="veral"><IcAlerta size={16} /> Ver alertas vigentes (3)</div>
    </div>
  );
}
