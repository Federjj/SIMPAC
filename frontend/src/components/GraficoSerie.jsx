import { useMemo } from "react";
import { escalaY, horaCorta, ticksTiempo } from "@/lib/historico";
import { NIVEL_HEX } from "@/map/palette";

// Gráfico SVG propio (sin librerías) para el histórico de una estación.
//   tipo "rio":    línea del caudal o nivel con las líneas de umbral de alerta y de emergencia.
//   tipo "lluvia": barras de mm por hora y, si hay, la temperatura como línea (eje derecho).
// Las horas van en hora de Perú. La tabla de la página es la alternativa de texto.
const W = 640;
const H = 260;
const MT = 14;
const MB = 30;
const ML = 46;

const num = (v) => Number(v).toLocaleString("es-PE", { maximumFractionDigits: 2 });

export default function GraficoSerie({ tipo, puntos = [], umbralAlerta = null, umbralEmergencia = null, unidad = "", desdeMs, hastaMs, rango, resumen }) {
  const mr = tipo === "lluvia" && puntos.some((p) => p.temp != null) ? 44 : 14;
  const ancho = W - ML - mr;
  const alto = H - MT - MB;
  const x = (t) => ML + ((t - desdeMs) / Math.max(1, hastaMs - desdeMs)) * ancho;
  const ticksX = useMemo(() => ticksTiempo(desdeMs, hastaMs, rango), [desdeMs, hastaMs, rango]);
  const etiquetaX = (t) => {
    const h = horaCorta(t); // "14/10 06:00"
    return rango === "24h" ? h.slice(6) : h.slice(0, 5);
  };

  if (tipo === "rio") {
    const e = escalaY([...puntos.map((p) => p.v), umbralAlerta, umbralEmergencia]);
    const y = (v) => MT + (1 - (v - e.min) / (e.max - e.min)) * alto;
    // segmentos: la línea se corta si pasan más de 12 h sin dato
    const segmentos = [];
    let actual = [];
    for (const p of puntos) {
      if (actual.length && p.t - actual[actual.length - 1].t > 12 * 3_600_000) {
        segmentos.push(actual);
        actual = [];
      }
      actual.push(p);
    }
    if (actual.length) segmentos.push(actual);
    const d = (seg) => seg.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)},${y(p.v).toFixed(1)}`).join(" ");
    return (
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={resumen} className="h-auto w-full">
        {e.ticks.map((t) => (
          <g key={t}>
            <line x1={ML} x2={W - mr} y1={y(t)} y2={y(t)} stroke="#e5e7eb" />
            <text x={ML - 6} y={y(t) + 3} fontSize="10" textAnchor="end" fill="#6b7280">
              {num(t)}
            </text>
          </g>
        ))}
        {ticksX.map((t) => (
          <text key={t} x={x(t)} y={H - 10} fontSize="10" textAnchor="middle" fill="#6b7280">
            {etiquetaX(t)}
          </text>
        ))}
        {umbralAlerta != null && (
          <g>
            <line x1={ML} x2={W - mr} y1={y(umbralAlerta)} y2={y(umbralAlerta)} stroke={NIVEL_HEX.alerta} strokeDasharray="6 4" strokeWidth="1.5" />
            <text x={W - mr - 2} y={y(umbralAlerta) - 4} fontSize="10" textAnchor="end" fill={NIVEL_HEX.alerta}>
              alerta {num(umbralAlerta)}
            </text>
          </g>
        )}
        {umbralEmergencia != null && (
          <g>
            <line x1={ML} x2={W - mr} y1={y(umbralEmergencia)} y2={y(umbralEmergencia)} stroke={NIVEL_HEX.emergencia} strokeDasharray="6 4" strokeWidth="1.5" />
            <text x={W - mr - 2} y={y(umbralEmergencia) - 4} fontSize="10" textAnchor="end" fill={NIVEL_HEX.emergencia}>
              emergencia {num(umbralEmergencia)}
            </text>
          </g>
        )}
        {segmentos.map((seg, i) => (
          <g key={i}>
            {seg.length > 1 && <path d={`${d(seg)} L${x(seg[seg.length - 1].t).toFixed(1)},${y(e.min)} L${x(seg[0].t).toFixed(1)},${y(e.min)} Z`} fill="#1C7ED6" fillOpacity="0.12" />}
            <path d={d(seg)} fill="none" stroke="#1C7ED6" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
            {seg.length === 1 && <circle cx={x(seg[0].t)} cy={y(seg[0].v)} r="3" fill="#1C7ED6" />}
          </g>
        ))}
        {puntos.length > 0 && (
          <circle cx={x(puntos[puntos.length - 1].t)} cy={y(puntos[puntos.length - 1].v)} r="4" fill="#fff" stroke="#1C7ED6" strokeWidth="2" />
        )}
        <text x={ML} y={10} fontSize="10" fill="#6b7280">
          {unidad}
        </text>
      </svg>
    );
  }

  // lluvia
  const mm = puntos.filter((p) => p.mm != null);
  const temps = puntos.filter((p) => p.temp != null);
  const e = escalaY(mm.map((p) => p.mm));
  const y = (v) => MT + (1 - (v - e.min) / (e.max - e.min)) * alto;
  const et = escalaY(temps.map((p) => p.temp), { desdeCero: false });
  const yt = (v) => MT + (1 - (v - et.min) / (et.max - et.min)) * alto;
  const horas = Math.max(1, (hastaMs - desdeMs) / 3_600_000);
  const wBarra = Math.max(1.5, ancho / horas - 1);
  const dTemp = temps.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)},${yt(p.temp).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={resumen} className="h-auto w-full">
      {e.ticks.map((t) => (
        <g key={t}>
          <line x1={ML} x2={W - mr} y1={y(t)} y2={y(t)} stroke="#e5e7eb" />
          <text x={ML - 6} y={y(t) + 3} fontSize="10" textAnchor="end" fill="#6b7280">
            {num(t)}
          </text>
        </g>
      ))}
      {temps.length > 0 &&
        et.ticks.map((t) => (
          <text key={`t${t}`} x={W - mr + 6} y={yt(t) + 3} fontSize="10" fill="#c2410c">
            {num(t)}°
          </text>
        ))}
      {ticksX.map((t) => (
        <text key={t} x={x(t)} y={H - 10} fontSize="10" textAnchor="middle" fill="#6b7280">
          {etiquetaX(t)}
        </text>
      ))}
      {mm.map((p) => (
        <rect key={p.t} x={x(p.t) - wBarra} y={y(p.mm)} width={wBarra} height={Math.max(0, y(e.min) - y(p.mm))} fill="#1C7ED6" opacity={p.mm > 0 ? 0.9 : 0.25}>
          <title>{`${horaCorta(p.t)}: ${num(p.mm)} mm`}</title>
        </rect>
      ))}
      {temps.length > 1 && <path d={dTemp} fill="none" stroke="#c2410c" strokeWidth="1.5" />}
      <text x={ML} y={10} fontSize="10" fill="#6b7280">
        mm por hora
      </text>
      {temps.length > 0 && (
        <text x={W - mr + 6} y={10} fontSize="10" fill="#c2410c">
          °C
        </text>
      )}
    </svg>
  );
}
