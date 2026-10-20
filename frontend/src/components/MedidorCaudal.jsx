import { useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowUp, Minus } from "lucide-react";
import { cn } from "@/lib/utils";
import { useContador } from "@/hooks/useContador";
import { lecturaRio, textoRio } from "@/lib/lenguaje";
import { COLOR_ESTADO, GRIS, anguloAguja, escalaMedidor, puntoArco, trazoArco } from "@/lib/medidor";
import { diaLegible, horasDesde } from "@/lib/tiempo";

// Medidor del caudal (o nivel) de la estación de ANA de un río vigilado frente a sus umbrales:
// un arco de 180 grados con los tramos verde (hasta el 80 % del nivel de alerta), ámbar, naranja
// (desde el nivel de alerta) y rojo (desde el de emergencia), las marcas "alerta 14" y
// "emergencia 18", un arco de progreso del color del estado y el número grande al centro. La
// escala y los tramos salen de lib/medidor.js (con prueba); los textos, de textoRio (lenguaje.js).
//   c       fila de caudal_actual (con la simulación de desarrollo aplicada, si la hay)
//   rio     el río vigilado (nombre)
//   viejo   true si la ingesta está atrasada (p.desactualizado): la hora se pinta en naranja
const CX = 160;
const CY = 150;
const R = 120;
const GROSOR = 18;
const TENDENCIA = { Ascendente: ["subiendo", ArrowUp], Descendente: ["bajando", ArrowDown], Estable: ["estable", Minus] };
const DIA_MS = 86_400_000;

function Marca({ m }) {
  const [x1, y1] = puntoArco(CX, CY, R + GROSOR / 2 + 2, m.fraccion);
  const [x2, y2] = puntoArco(CX, CY, R + GROSOR / 2 + 9, m.fraccion);
  const [tx, ty] = puntoArco(CX, CY, R + GROSOR / 2 + 22, m.fraccion);
  const izquierda = m.fraccion < 0.5;
  return (
    <g>
      <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="currentColor" strokeWidth="1.5" />
      <text x={tx} y={ty + 3} fontSize="10" fill="currentColor" textAnchor={izquierda ? "end" : "start"} className="fill-current">
        {m.texto}
      </text>
    </g>
  );
}

export default function MedidorCaudal({ c, rio, viejo = false, className }) {
  const t = c ? textoRio(c) : null;
  const e = escalaMedidor(c);
  const color = t ? COLOR_ESTADO[t.estado] ?? GRIS : GRIS;
  const fuerte = t && !t.bajo && (t.estado === "alerta" || t.estado === "emergencia");
  // el arco se dibuja al entrar en pantalla (IntersectionObserver) y cada vez que cambia el valor
  const ref = useRef(null);
  const [visto, setVisto] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") {
      setVisto(true);
      return undefined;
    }
    const io = new IntersectionObserver(
      (entradas) => entradas.some((x) => x.isIntersecting) && (setVisto(true), io.disconnect()),
      { threshold: 0.3 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  const fraccion = visto ? e.fraccion : 0;
  const valor = useContador(visto ? c?.valor ?? null : 0, { dur: 900 });
  const decimales = c?.valor != null && c.valor < 10 ? 2 : c?.valor < 100 ? 1 : 0;
  const numero = valor == null ? null : Number(valor).toLocaleString("es-PE", { minimumFractionDigits: decimales, maximumFractionDigits: decimales });
  const [nombreT, IconoT] = TENDENCIA[c?.tendencia] ?? [null, null];
  // dato de ayer o más viejo: se dice
  const lectura = c ? lecturaRio(c) : null;
  const fechaMs = c?.fecha ? Date.parse(`${c.fecha}T${(c.hora ?? "00:00").slice(0, 5)}:00-05:00`) : NaN;
  const atrasado = viejo || (Number.isFinite(fechaMs) && Date.now() - fechaMs > DIA_MS);

  return (
    <section ref={ref} className={cn("px-4 pt-3", className)} aria-label={`Medidor del ${rio?.nombre ?? "río"}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <h3 className="text-[0.68rem] uppercase tracking-wider text-muted-foreground">
          {rio?.nombre ?? "Río"} · estación {c?.estacion ?? rio?.estacion_ana ?? "ANA"} (ANA)
        </h3>
        {nombreT && (
          <span className="inline-flex items-center gap-1 text-[0.7rem] text-muted-foreground">
            <IconoT className="h-3.5 w-3.5" aria-hidden="true" />
            {nombreT}
          </span>
        )}
      </div>
      <div className="mx-auto mt-1 max-w-[320px]">
        <svg
          viewBox="0 0 320 175"
          className="block h-auto w-full text-muted-foreground"
          role="img"
          aria-label={
            t
              ? `${t.titulo}: ${t.etiqueta}. ${t.frase}`
              : "Sin medición"
          }
        >
          {/* fondo: los tramos de la escala (o gris si no hay umbral o medición) */}
          {e.tramos.length ? (
            e.tramos.map((tr, i) => (
              <path
                key={i}
                d={trazoArco(CX, CY, R, tr.desde / e.max, tr.hasta / e.max)}
                fill="none"
                stroke={tr.color}
                strokeOpacity="0.28"
                strokeWidth={GROSOR}
              />
            ))
          ) : (
            <path d={trazoArco(CX, CY, R, 0, 1)} fill="none" stroke={GRIS} strokeOpacity="0.3" strokeWidth={GROSOR} />
          )}
          {/* progreso: el arco del color del estado se dibuja con stroke-dashoffset */}
          {e.modo !== "sin_medicion" && (
            <path
              d={trazoArco(CX, CY, R, 0, 1)}
              fill="none"
              stroke={color}
              strokeWidth={GROSOR}
              strokeLinecap="butt"
              pathLength="100"
              strokeDasharray="100 100"
              strokeDashoffset={100 - fraccion * 100}
              className={cn("med-progreso", fuerte && "med-late")}
            />
          )}
          {e.marcas.map((m) => (
            <Marca key={m.texto} m={m} />
          ))}
          {/* aguja: gira desde el pivote (el g exterior la lleva al centro; el interior rota) */}
          {e.modo !== "sin_medicion" && (
            <g transform={`translate(${CX} ${CY})`}>
              <g className="med-aguja" style={{ transform: `rotate(${anguloAguja(fraccion)}deg)` }}>
                <line x1="0" y1="0" x2="0" y2={-(R - GROSOR / 2 - 6)} stroke="#0F172A" strokeWidth="2.5" strokeLinecap="round" />
                <circle cx="0" cy="0" r="5" fill="#0F172A" />
              </g>
            </g>
          )}
          <text x={CX} y={CY - 28} textAnchor="middle" className="med-numero" style={{ fill: e.modo === "sin_medicion" ? GRIS : "#0F172A" }}>
            {numero ?? "Sin medición"}
          </text>
          {numero != null && (
            <text x={CX} y={CY - 10} textAnchor="middle" fontSize="12" fill="currentColor">
              {c.unidad}
            </text>
          )}
          <text x={CX} y={CY + 12} textAnchor="middle" fontSize="13" fontWeight="600" style={{ fill: e.modo === "sin_medicion" ? GRIS : color === GRIS ? "#6B7280" : color }}>
            {t ? (t.estado === "atento" ? "Cerca del nivel de alerta" : t.etiqueta) : "Sin medición"}
          </text>
        </svg>
      </div>
      <p className="mt-1 text-sm leading-snug">
        {t?.frase ?? "ANA no tiene una medición reciente de esta estación."}
        {t?.accion && fuerte && <span className="block font-semibold">{t.accion}</span>}
      </p>
      <p className={cn("mt-1 text-[0.7rem]", atrasado ? "font-medium text-nivel-alerta" : "text-muted-foreground")}>
        {lectura ? (atrasado ? `Último dato: ${c.fecha ? diaLegible(c.fecha) : ""} ${c.hora ?? ""} (ANA); puede haber cambiado.` : lectura) : "ANA: sin hora de lectura."}
        {t?.estado === "atento" && !t.bajo && <span className="block">“Cerca” es un criterio de SIMPAC (80 % del caudal de alerta), no un aviso de ANA.</span>}
        {Number.isFinite(fechaMs) && !atrasado && horasDesde(new Date(fechaMs).toISOString()) >= 3 && <span className="block">Hace más de 3 h: ANA publica por horas y a veces con atraso.</span>}
      </p>
    </section>
  );
}
