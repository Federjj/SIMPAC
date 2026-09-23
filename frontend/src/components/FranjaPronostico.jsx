import { useState } from "react";
import { cn } from "@/lib/utils";
import Glifo from "@/components/Glifo";
import { aspecto, emitidoTexto } from "@/lib/pronostico";
import { DIAS_CORTOS, diaMesCorto, diaSemana } from "@/lib/tiempo";

// Franja de 3 días del panel de estado: el pronóstico oficial de SENAMHI para tu localidad (la
// de la ciudad elegida o la más cercana a tu GPS), con su ícono, una frase corta y las
// temperaturas. Tocar un día muestra el texto de SENAMHI tal cual. `pron` viene de
// hooks/usePronosticoLocal; `fechaMapa` es el día elegido en el mapa (se marca).

// Clases literales (Tailwind las genera solo si aparecen enteras en el código).
const FONDO = {
  lluvia: "from-sky-50 border-sky-200",
  tormenta: "from-indigo-50 border-indigo-200",
  nieve: "from-cyan-50 border-cyan-200",
  sol: "from-amber-50 border-amber-200",
  nublado: "from-slate-50 border-slate-200",
};
const fondo = (a) => cn(FONDO[a.clase === "seco" ? (a.sol ? "sol" : "nublado") : a.clase], a.posible && "border-dashed border-sky-300");

const PIE =
  "Ícono y resumen de SIMPAC, basados en SENAMHI. Es el pronóstico para la localidad, no para todo el departamento. " +
  "Toca un día para leer el texto de SENAMHI.";

function Temps({ fila, className }) {
  if (fila.tmax == null && fila.tmin == null) return <span className={className}>–</span>;
  return (
    <span className={cn("tabular-nums", className)}>
      <span className="font-semibold text-foreground">{fila.tmax != null ? `${fila.tmax}°` : "–"}</span>{" "}
      <span className="text-sky-700">{fila.tmin != null ? `${fila.tmin}°` : "–"}</span>
    </span>
  );
}

function Dia({ d, abierto, elegido, onToggle }) {
  if (!d.fila) {
    return (
      <div className="flex h-full flex-col items-center rounded-xl border border-dashed border-border p-2 text-center sm:p-2.5">
        <div className="text-[0.72rem] font-semibold">{d.etiqueta}</div>
        <div className="text-[0.66rem] text-muted-foreground">{d.fechaCorta}</div>
        <div className="my-1 grid h-9 w-9 place-items-center text-lg font-semibold text-muted-foreground sm:h-11 sm:w-11">?</div>
        <div className="text-[0.72rem] leading-tight text-muted-foreground">Sin pronóstico para este día</div>
      </div>
    );
  }
  const a = aspecto(d.fila);
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={abierto}
      className={cn(
        "flex h-full flex-col items-center rounded-xl border bg-gradient-to-b to-card p-2 text-center transition-shadow hover:shadow-md sm:p-2.5",
        fondo(a),
        elegido && "ring-2 ring-foreground/80",
        abierto && "shadow-md"
      )}
    >
      <span className="text-[0.72rem] font-semibold">{d.etiqueta}</span>
      <span className="text-[0.66rem] text-muted-foreground">{d.fechaCorta}</span>
      <Glifo nombre={a.glifo} className="mx-auto my-1 h-9 w-9 sm:h-11 sm:w-11" />
      <span className="line-clamp-2 text-[0.78rem] font-medium leading-tight sm:text-sm">{a.corto}</span>
      {a.extra && <span className="text-[0.66rem] text-indigo-700">{a.extra}</span>}
      <Temps fila={d.fila} className="mt-auto pt-1 text-sm" />
    </button>
  );
}

export default function FranjaPronostico({ pron, fechaMapa }) {
  const [abierto, setAbierto] = useState(null);
  if (!pron || pron.estado === "sin_servicio") return null;
  const { estado, localidad, dias, emision } = pron;
  const conDatos = estado === "ok" || estado === "cercana";
  const km = localidad?.km != null ? Math.round(localidad.km) : null;
  const diaAbierto = dias.find((d) => d.fecha === abierto && d.fila);

  return (
    <section className="px-4 pt-2">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <div className="text-[0.68rem] uppercase tracking-wider text-muted-foreground">
          Pronóstico de SENAMHI{conDatos && localidad?.nombre ? ` · ${localidad.nombre}` : ""}
          {estado === "cercana" && km != null && <span className="normal-case tracking-normal">, a {km} km</span>}
        </div>
        {conDatos && (
          <div className="text-[0.68rem] text-muted-foreground">
            {emitidoTexto(emision)}
            {localidad?.url && (
              <>
                {" · "}
                <a href={localidad.url} target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">
                  Ver en SENAMHI
                </a>
              </>
            )}
          </div>
        )}
      </div>

      {estado === "cercana" && (
        <p className="mt-0.5 text-xs text-muted-foreground">
          Es la localidad con pronóstico más cercana a tu ubicación. En tu zona el tiempo puede ser distinto.
        </p>
      )}

      {estado === "cargando" && (
        <div className="mt-1.5 grid grid-cols-3 gap-2">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-[118px] animate-pulse rounded-xl bg-muted" />
          ))}
        </div>
      )}
      {estado === "error" && <p className="mt-1 text-sm text-muted-foreground">No se pudo cargar el pronóstico de SENAMHI.</p>}
      {estado === "sin_datos" && (
        <p className="mt-1 text-sm text-muted-foreground">
          El pronóstico de SENAMHI para {localidad?.nombre || "tu localidad"} no está disponible ahora.
        </p>
      )}
      {estado === "lejos" && (
        <p className="mt-1 text-sm text-muted-foreground">
          SENAMHI no publica pronóstico por localidad cerca de aquí (la más cercana es {localidad?.nombre}, a {km} km). Revisa
          los avisos del mapa.
        </p>
      )}

      {conDatos && (
        <>
          <div className="mt-1.5 grid grid-cols-3 gap-2">
            {dias.map((d) => (
              <Dia
                key={d.fecha}
                d={d}
                elegido={d.fecha === fechaMapa}
                abierto={abierto === d.fecha}
                onToggle={() => setAbierto((x) => (x === d.fecha ? null : d.fecha))}
              />
            ))}
          </div>
          {diaAbierto && (
            <p className="mt-1.5 text-xs text-muted-foreground">
              <span className="font-medium text-foreground">{diaAbierto.etiqueta}:</span> SENAMHI dice: «{diaAbierto.fila.texto}»
            </p>
          )}
          {pron.atrasado && (
            <p className="mt-1.5 text-xs text-nivel-alerta">
              SENAMHI no publica un pronóstico más nuevo desde el {diaMesCorto(emision)} (no lo actualiza los fines de semana ni
              feriados).
            </p>
          )}
          <p className="mt-1.5 text-[0.66rem] leading-snug text-muted-foreground">{PIE}</p>
        </>
      )}
    </section>
  );
}

// Versión corta, con el panel plegado: "Hoy [glifo] 21°/10° · Mañana [glifo] 22°/9°" (y pasado desde sm).
export function FranjaMini({ pron }) {
  if (!pron || (pron.estado !== "ok" && pron.estado !== "cercana")) return null;
  const dias = pron.dias.filter((d) => d.fila);
  if (!dias.length) return null;
  return (
    <div className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-xs text-muted-foreground">
      {pron.dias.map((d, i) => {
        if (!d.fila) return null;
        const etiqueta = i === 2 ? DIAS_CORTOS[diaSemana(d.fecha)].replace(/^./, (c) => c.toUpperCase()) : d.etiqueta;
        return (
          <span key={d.fecha} className={cn("inline-flex items-center gap-1", i === 2 && "hidden sm:inline-flex")}>
            {i > 0 && <span aria-hidden="true">·</span>}
            <span className="font-medium text-foreground">{etiqueta}</span>
            <Glifo nombre={aspecto(d.fila).glifo} className="h-4 w-4" />
            <span className="tabular-nums">
              {d.fila.tmax ?? "–"}°/{d.fila.tmin ?? "–"}°
            </span>
          </span>
        );
      })}
    </div>
  );
}
