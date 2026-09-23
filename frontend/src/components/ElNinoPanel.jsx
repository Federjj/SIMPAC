import { useEffect, useRef, useState } from "react";
import { ChevronRight, History, ShieldAlert, Thermometer, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { getIcenSerie } from "@/lib/queries";
import { MESES, MESES_CORTOS } from "@/lib/tiempo";
import { ENFEN_HEX } from "@/map/palette";

// El Niño costero en gráficos: en qué paso está el Sistema de Alerta del ENFEN, cómo viene
// el mar frente a la costa norte mes a mes (ICEN) y cómo llovió en otros El Niño.

const PASOS = [
  { id: "Sin alerta", explica: "No se espera El Niño ni La Niña" },
  { id: "Vigilancia", explica: "Podría formarse en los próximos meses" },
  { id: "Alerta", explica: "Ya está en curso o es inminente" },
];

// Categorías del ICEN (Nota Técnica ENFEN 01-2024) con palabras de todos los días.
const CLASES_ICEN = [
  { id: "fria", color: "#3B82F6", texto: "Frío" },
  { id: "neutra", color: "#9CA3AF", texto: "Normal" },
  { id: "debil", color: "#FACC15", texto: "Caliente débil" },
  { id: "moderada", color: "#F97316", texto: "Caliente moderado" },
  { id: "fuerte", color: "#DC2626", texto: "Muy caliente (fuerte)" },
  { id: "extraordinaria", color: "#7F1D1D", texto: "Extraordinario" },
];

function claseIcen(categoria) {
  const c = (categoria ?? "").toLowerCase();
  const id = /^fr[íi]/.test(c)
    ? "fria"
    : !/^c[áa]lid/.test(c)
      ? "neutra"
      : c.includes("extraordinari")
        ? "extraordinaria"
        : c.includes("fuerte")
          ? "fuerte"
          : c.includes("moderad")
            ? "moderada"
            : "debil";
  return CLASES_ICEN.find((k) => k.id === id);
}

const calida = (p) => /^c[áa]lid/i.test(p.categoria ?? "");
const signo = (v) => (v >= 0 ? "+" : "") + v.toFixed(2);
const mesLargo = (mes) => `${MESES[Number(mes.slice(5, 7)) - 1]} ${mes.slice(0, 4)}`;

function Pasos({ actual, quien }) {
  const i = PASOS.findIndex((p) => p.id === actual);
  return (
    <ol className="flex items-stretch gap-1" aria-label={`Sistema de alerta ENFEN: ${actual ?? "sin dato"}`}>
      {PASOS.map((p, k) => {
        const color = ENFEN_HEX[p.id];
        const activo = k === i;
        return (
          <li key={p.id} className="flex flex-1 items-center gap-1">
            <div
              className={cn(
                "flex h-full flex-1 flex-col justify-center rounded-lg border px-2 py-1.5 text-center",
                activo ? "font-semibold shadow-md" : "border-border text-muted-foreground"
              )}
              style={activo ? { background: color, borderColor: color, color: p.id === "Vigilancia" ? "#1F2937" : "#fff" } : undefined}
              aria-current={activo ? "step" : undefined}
            >
              <span className="text-xs sm:text-sm">{p.id}</span>
              <span className={cn("text-[0.62rem] leading-tight", activo ? "opacity-90" : "")}>
                {p.id === "Sin alerta" ? p.explica : `${quien}: ${p.explica.toLowerCase()}`}
              </span>
            </div>
            {k < PASOS.length - 1 && <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />}
          </li>
        );
      })}
    </ol>
  );
}

// Barras del ICEN mes a mes; el estimado del ENFEN (ICEN temporal) va punteado al final.
function GraficoIcen({ puntos }) {
  const W = 640;
  const H = 240;
  const M = { izq: 30, der: 58, arr: 14, aba: 44 }; // abajo: mes, año y "estimado"
  const vals = puntos.map((p) => p.valor);
  const yMin = Math.floor(Math.min(-1, ...vals));
  const yMax = Math.ceil(Math.max(2, ...vals));
  const alto = H - M.arr - M.aba;
  const y = (v) => M.arr + ((yMax - v) / (yMax - yMin)) * alto;
  const paso = (W - M.izq - M.der) / puntos.length;
  const ancho = Math.max(4, paso * 0.72);
  const x = (k) => M.izq + k * paso + (paso - ancho) / 2;
  const marcas = [];
  for (let v = yMin; v <= yMax; v++) marcas.push(v);
  const ultimoReal = puntos.length - 1 - puntos.filter((p) => p.estimado).length; // los estimados van al final
  const lineas = [
    { v: 0.5, texto: "cálido", color: "#F58E27" },
    ...(yMin < -0.7 ? [{ v: -0.7, texto: "frío", color: "#3B82F6" }] : []),
  ];

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="h-auto w-full"
      role="img"
      aria-label={`ICEN de ${mesLargo(puntos[0].mes)} a ${mesLargo(puntos[puntos.length - 1].mes)}`}
    >
      {marcas.map((v) => (
        <g key={v}>
          <line x1={M.izq} x2={W - M.der} y1={y(v)} y2={y(v)} stroke="currentColor" strokeOpacity={v === 0 ? 0.45 : 0.1} />
          <text x={M.izq - 6} y={y(v) + 4} textAnchor="end" fontSize="11" fill="currentColor" fillOpacity="0.6">
            {v > 0 ? `+${v}` : v}
          </text>
        </g>
      ))}
      {lineas.map((l) => (
        <g key={l.v}>
          <line x1={M.izq} x2={W - M.der} y1={y(l.v)} y2={y(l.v)} stroke={l.color} strokeDasharray="5 4" strokeWidth="1.5" />
          <text x={W - M.der + 6} y={y(l.v) + 4} fontSize="11" fill={l.color} fontWeight="600">
            {l.texto}
          </text>
        </g>
      ))}
      {puntos.map((p, k) => {
        const { color, texto } = claseIcen(p.categoria);
        const m = Number(p.mes.slice(5, 7));
        // una etiqueta cada 3 meses contando desde el último; el año, en la primera de cada año
        const etiqueta = (puntos.length - 1 - k) % 3 === 0;
        const conAnio = etiqueta && !puntos.some((q, j) => j < k && (puntos.length - 1 - j) % 3 === 0 && q.mes.slice(0, 4) === p.mes.slice(0, 4));
        const arriba = y(Math.max(p.valor, 0));
        const altoBarra = Math.max(1, Math.abs(y(p.valor) - y(0)));
        const conValor = k === ultimoReal || p.estimado;
        // con un estimado al lado, los dos valores se separan: el real hacia la izquierda y el
        // estimado hacia la derecha (si no, se pisan: cada barra mide unos 16 px)
        const juntos = puntos.some((q) => q.estimado) && (k === ultimoReal || p.estimado);
        const ancla = !juntos ? "middle" : p.estimado ? "start" : "end";
        const xValor = !juntos ? x(k) + ancho / 2 : p.estimado ? x(k) : x(k) + ancho;
        return (
          <g key={p.mes}>
            <rect
              x={x(k)}
              y={arriba}
              width={ancho}
              height={altoBarra}
              rx="2"
              fill={color}
              fillOpacity={p.estimado ? 0.3 : 0.95}
              stroke={p.estimado ? color : "none"}
              strokeDasharray={p.estimado ? "4 3" : undefined}
              strokeWidth="1.5"
            >
              <title>
                {`${mesLargo(p.mes)}: ${signo(p.valor)} (${texto.toLowerCase()}${p.estimado ? ", estimado del ENFEN" : `, ${p.origen}`})`}
              </title>
            </rect>
            {conValor && (
              <text
                x={xValor}
                y={p.valor >= 0 ? arriba - 4 : arriba + altoBarra + 12}
                textAnchor={ancla}
                fontSize="11"
                fontWeight="700"
                fill="currentColor"
              >
                {signo(p.valor)}
              </text>
            )}
            {etiqueta && (
              <text x={x(k) + ancho / 2} y={H - M.aba + 16} textAnchor="middle" fontSize="11" fill="currentColor" fillOpacity="0.7">
                {MESES_CORTOS[m - 1]}
                {conAnio && (
                  <tspan x={x(k) + ancho / 2} dy="12">
                    {p.mes.slice(0, 4)}
                  </tspan>
                )}
              </text>
            )}
            {p.estimado && (
              <text
                x={x(k) + ancho / 2}
                y={H - M.aba + (conAnio ? 40 : 28)}
                textAnchor="middle"
                fontSize="10"
                fill="currentColor"
                fillOpacity="0.6"
              >
                estimado
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

// "Van 6 meses seguidos con el mar más caliente..." a partir de la serie.
function resumenSerie(reales) {
  if (!reales.length) return null;
  let racha = 0;
  for (let k = reales.length - 1; k >= 0 && calida(reales[k]); k--) racha++;
  const ultimo = reales[reales.length - 1];
  const previo = reales[reales.length - 2];
  const rumbo =
    previo && racha > 0
      ? ultimo.valor > previo.valor + 0.1
        ? " y sigue calentándose"
        : ultimo.valor < previo.valor - 0.1
          ? ", aunque empieza a enfriarse"
          : ""
      : "";
  if (racha >= 2) return `Van ${racha} meses seguidos con el mar más caliente de lo normal frente a la costa norte${rumbo}.`;
  if (racha === 1) return `En ${mesLargo(ultimo.mes)} el mar frente a la costa norte pasó a estar más caliente de lo normal.`;
  return `En ${mesLargo(ultimo.mes)} el mar frente a la costa norte no estaba más caliente de lo normal.`;
}

const EVENTOS = [
  { valor: "1997-1998", texto: "1997-1998" },
  { valor: "2017", texto: "2017 (costero)" },
  { valor: "2023", texto: "2023 (costero)" },
];

export default function ElNinoPanel({ enfen, mar, icen, icenTmp, onVerEvento, onCerrar }) {
  const [serie, setSerie] = useState(null);
  useEffect(() => {
    let vivo = true;
    getIcenSerie(24)
      .then((s) => vivo && setSerie(s))
      .catch(() => vivo && setSerie([])); // sin serie: se grafica al menos el último mes
    return () => {
      vivo = false;
    };
  }, []);

  // Diálogo modal: Escape cierra, el foco entra al abrir (botón Cerrar), Tab no sale del
  // diálogo y al cerrar vuelve a donde estaba (el chip o el botón de la barra lateral).
  const dialogo = useRef(null);
  const cerrar = useRef(null);
  useEffect(() => {
    const antes = document.activeElement;
    cerrar.current?.focus();
    return () => antes?.focus?.();
  }, []);
  useEffect(() => {
    const alTeclado = (e) => {
      if (e.key === "Escape") onCerrar();
      if (e.key !== "Tab" || !dialogo.current) return;
      const focos = dialogo.current.querySelectorAll("button, [href], select, [tabindex]:not([tabindex='-1'])");
      const primero = focos[0];
      const ultimo = focos[focos.length - 1];
      if (e.shiftKey && document.activeElement === primero) {
        e.preventDefault();
        ultimo.focus();
      } else if (!e.shiftKey && document.activeElement === ultimo) {
        e.preventDefault();
        primero.focus();
      }
    };
    window.addEventListener("keydown", alTeclado);
    return () => window.removeEventListener("keydown", alTeclado);
  }, [onCerrar]);

  const reales = serie?.length
    ? serie
    : icen
      ? [{ mes: icen.periodo, valor: icen.valor, categoria: icen.categoria, origen: icen.origen }]
      : [];
  const ultimoMes = reales[reales.length - 1]?.mes;
  const estimado =
    icenTmp && ultimoMes && icenTmp.periodo > ultimoMes
      ? [{ mes: icenTmp.periodo, valor: icenTmp.valor, categoria: icenTmp.categoria, estimado: true }]
      : [];
  const puntos = [...reales, ...estimado];
  // la racha solo se cuenta con la serie completa (con un solo mes diría "pasó a estar")
  const resumen = serie?.length ? resumenSerie(reales) : null;

  return (
    <div className="absolute inset-0 z-[1100] flex items-start justify-center overflow-y-auto bg-black/40 p-3 backdrop-blur-[2px] md:items-center md:p-6">
      <section
        ref={dialogo}
        role="dialog"
        aria-modal="true"
        aria-labelledby="elnino-titulo"
        className="w-full max-w-2xl rounded-2xl border border-border bg-card shadow-2xl"
      >
        <header className="flex items-start gap-3 border-b border-border px-4 py-3">
          <div
            className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-white"
            style={{ background: ENFEN_HEX[enfen?.corto] ?? "#9CA3AF" }}
          >
            <ShieldAlert className="h-[18px] w-[18px]" />
          </div>
          <div className="min-w-0 leading-tight">
            <h2 id="elnino-titulo" className="text-base font-semibold md:text-lg">
              {enfen ? enfen.titulo.charAt(0).toUpperCase() + enfen.titulo.slice(1) : "El Niño costero"}
            </h2>
            <p className="text-xs text-muted-foreground">{enfen?.fuente ?? "Sistema de alerta ENFEN"}</p>
          </div>
          <Button ref={cerrar} variant="ghost" size="icon" className="ml-auto shrink-0" onClick={onCerrar} aria-label="Cerrar">
            <X className="h-4 w-4" />
          </Button>
        </header>

        <div className="space-y-5 px-4 py-4">
          <div className="space-y-2">
            <h3 className="text-[0.68rem] font-semibold uppercase tracking-widest text-muted-foreground">
              Sistema de alerta del ENFEN
            </h3>
            <Pasos actual={enfen?.corto} quien={enfen?.quien ?? "El Niño costero"} />
            {enfen && (
              <p className="text-sm leading-snug">
                {enfen.explica} {enfen.accion}
              </p>
            )}
            {enfen?.atrasado && <p className="text-xs text-nivel-alerta">Puede haber un comunicado más nuevo.</p>}
          </div>

          <div className="space-y-2">
            <h3 className="flex items-center gap-1.5 text-[0.68rem] font-semibold uppercase tracking-widest text-muted-foreground">
              <Thermometer className="h-3.5 w-3.5" />
              Temperatura del mar frente a la costa norte
            </h3>
            {resumen && <p className="text-sm font-medium leading-snug">{resumen}</p>}
            {puntos.length ? (
              <GraficoIcen puntos={puntos} />
            ) : (
              <p className="text-sm text-muted-foreground">{serie ? "Sin datos del ICEN todavía." : "Cargando…"}</p>
            )}
            <div className="flex flex-wrap gap-x-3 gap-y-1">
              {CLASES_ICEN.map((k) => (
                <span key={k.id} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <span className="h-2.5 w-2.5 rounded-sm" style={{ background: k.color }} />
                  {k.texto}
                </span>
              ))}
            </div>
            <p className="text-xs leading-snug text-muted-foreground">
              Cada barra es un mes: mientras más alta y roja, más caliente está el mar. Sobre la línea naranja el mar
              está cálido, y si sigue así 3 meses seguidos el ENFEN lo cuenta como El Niño costero. Un mar caliente
              suele traer lluvias fuertes a la costa norte (Tumbes, Piura, Lambayeque, La Libertad) y a las partes altas
              que miran al mar, como el oeste de Cajamarca (Contumazá, San Miguel, Santa Cruz), sobre todo de diciembre
              a abril; en el resto de la sierra de Cajamarca el efecto es menor y cambia de un año a otro. Índice
              Costero El Niño (ICEN): ENFEN e IGP; la categoría es la oficial del ENFEN y, en los meses que solo
              publica el IGP, la calcula SIMPAC con los mismos cortes.
              {mar?.detalle ? ` ${mar.detalle}` : ""}
            </p>
          </div>

          <div className="space-y-2">
            <h3 className="flex items-center gap-1.5 text-[0.68rem] font-semibold uppercase tracking-widest text-muted-foreground">
              <History className="h-3.5 w-3.5" />
              Así llovió en otros El Niño
            </h3>
            <p className="text-sm leading-snug">
              Mira en el mapa dónde llovió mucho más de lo normal en el verano de otros El Niño. Cada evento fue
              distinto: sirve para ver qué zonas se afectaron antes, no para predecir este.
            </p>
            <div className="flex flex-wrap gap-2">
              {EVENTOS.map((e) => (
                <Button key={e.valor} variant="secondary" size="sm" onClick={() => onVerEvento(e.valor)}>
                  {e.texto}
                </Button>
              ))}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
