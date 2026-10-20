import { useEffect, useMemo, useState } from "react";
import { Droplets } from "lucide-react";
import { cn } from "@/lib/utils";
import { useContador, useMovimientoReducido } from "@/hooks/useContador";
import { getLluvia24h, getLluviaAhora } from "@/lib/queries";
import { codDeEstacion, escalaBarras, estacionesCercanas, resumenSerie, serie24, textoKm } from "@/lib/serie24h";
import { hhmmPeru, horaPeru } from "@/lib/tiempo";

// "Lluvia cerca de ti (SENAMHI)": arriba, una barra por cada una de las 3 estaciones automáticas
// más cercanas con la lluvia de la última hora frente a la referencia de SENAMHI de esa estación
// (lluvia_senamhi_actual); abajo, la serie de 24 barras (una por hora) de la más cercana
// (lectura_lluvia, hoy solo Cajamarca). Las horas sin dato son huecos, no ceros. Se monta recién
// al abrir la altura media de la hoja (así no pide nada al cargar la app); las dos consultas
// comparten la caché con el mapa y el panel.
//   origen   [lat, lon] desde donde se mide (GPS o centro de la ciudad)   porGps  si es el GPS
//   ciudad   nombre de la ciudad (para decir "desde el centro de X")        depto  departamento
//   revisada true si el worker revisó la lluvia (p.lluviaActualizada)      hora  p.lluviaActualizada
//   vieja    p.lluviaDesactualizada (más de 1,5 h sin correr)
const AMBAR = "#EAB308";
const AZUL = "#3BA5EB";
const GRIS = "#CBD5E1";
const num = (v) => Number(v).toLocaleString("es-PE", { maximumFractionDigits: 1 });

function BarraHora({ e, i, montado, max }) {
  const f = e.pp_1h == null ? 0 : Math.max(e.pp_1h / max, e.pp_1h > 0 ? 0.03 : 0);
  const mm = useContador(montado ? e.pp_1h ?? 0 : 0, { dur: 500 });
  const color = e.pasa ? AMBAR : AZUL;
  const fRef = e.umbral_1h != null ? Math.min(1, e.umbral_1h / max) : null;
  return (
    <li className="flex min-w-0 flex-col items-center text-center">
      <span className="tz-num text-sm font-semibold" style={{ color: e.pasa ? "#A16207" : undefined }}>
        {num(mm)} mm
      </span>
      <div className="relative mt-1 h-20 w-10 rounded-md bg-muted/70" aria-hidden="true">
        <div
          className={cn("bl-barra absolute inset-x-1 bottom-0 rounded-t-sm", !montado && "plegada")}
          style={{ "--f": f, "--i": i, height: "100%", background: color }}
        />
        {fRef != null && (
          <div className="bl-ref absolute inset-x-0 text-slate-700" style={{ bottom: `${fRef * 100}%` }} title={`Referencia de SENAMHI: ${num(e.umbral_1h)} mm en 1 h`} />
        )}
      </div>
      <span className="mt-1 line-clamp-2 text-[0.72rem] font-medium leading-tight">{e.corto}</span>
      <span className="text-[0.66rem] text-muted-foreground">
        {textoKm(e.km)}
        {e.umbral_1h != null && <> · ref. {num(e.umbral_1h)} mm</>}
      </span>
      {e.pasa && <span className="text-[0.66rem] font-semibold text-yellow-700">Atentos a la lluvia</span>}
    </li>
  );
}

function Serie({ serie, nombre, montado }) {
  const r = resumenSerie(serie);
  const esc = escalaBarras(serie.map((b) => b.mm));
  if (!r.conDato) return null;
  const pico = r.pico ? ` (lo más intenso: lluvia ${r.pico.clase} a las ${hhmmPeru(r.pico.hora)})` : "";
  return (
    <div className="mt-3">
      <p className="text-sm leading-snug">
        <span className="font-semibold">En 24 h: {num(r.total)} mm en {nombre}</span>
        {r.total > 0 ? pico : " (no llovió)"}.
        {r.conDato < 24 && <span className="text-muted-foreground"> {24 - r.conDato} {24 - r.conDato === 1 ? "hora" : "horas"} sin dato.</span>}
      </p>
      <ul className="mt-1.5 flex h-12 items-end gap-px" aria-label={`Lluvia por hora en ${nombre}, últimas 24 horas`}>
        {serie.map((b, i) => (
          <li
            key={b.hora.toISOString()}
            className="relative flex-1"
            style={{ height: "100%" }}
            title={`${hhmmPeru(b.hora)}: ${b.mm == null ? "sin dato" : `${num(b.mm)} mm`}`}
            aria-label={`${hhmmPeru(b.hora)}: ${b.mm == null ? "sin dato" : `${num(b.mm)} milímetros`}`}
          >
            {b.mm == null ? (
              <span className="absolute inset-x-0 bottom-0 h-full border-b border-dashed border-slate-300" aria-hidden="true" />
            ) : (
              <span
                className={cn("bl-barra absolute inset-x-0 bottom-0 rounded-t-[2px]", !montado && "plegada")}
                style={{ "--f": Math.max(esc.fraccion(b.mm), b.mm > 0 ? 0.06 : 0.02), "--i": i, height: "100%", background: b.mm > 0 ? AZUL : GRIS }}
                aria-hidden="true"
              />
            )}
          </li>
        ))}
      </ul>
      <div className="mt-0.5 flex justify-between text-[0.64rem] text-muted-foreground" aria-hidden="true">
        <span>hace 24 h</span>
        <span>hace 12 h</span>
        <span>ahora</span>
      </div>
    </div>
  );
}

export default function BarrasLluvia({ origen, porGps, ciudad, depto, revisada, hora, vieja, className }) {
  const [ahora, setAhora] = useState({ datos: null, error: false });
  const [filas24, setFilas24] = useState([]);
  const reducido = useMovimientoReducido();
  const [montado, setMontado] = useState(reducido);
  useEffect(() => {
    let vivo = true;
    getLluviaAhora()
      .then((d) => vivo && setAhora({ datos: Array.isArray(d) ? d : [], error: false }))
      .catch((e) => {
        console.error("lluvia ahora", e);
        if (vivo) setAhora({ datos: null, error: true });
      });
    if (depto) {
      getLluvia24h(depto)
        .then((f) => vivo && setFilas24(f ?? []))
        .catch(() => vivo && setFilas24([]));
    }
    // las barras crecen justo después de montar (transform scaleY); con setTimeout y no con
    // requestAnimationFrame, que no corre con la pestaña oculta
    const id = setTimeout(() => vivo && setMontado(true), 30);
    return () => {
      vivo = false;
      clearTimeout(id);
    };
  }, [depto]);

  const cercanas = useMemo(
    () => (origen && ahora.datos ? estacionesCercanas(ahora.datos, origen[0], origen[1], { n: 3 }) : []),
    [origen, ahora.datos]
  );
  const max = useMemo(() => {
    const vals = cercanas.flatMap((e) => [e.pp_1h, e.umbral_1h != null ? e.umbral_1h * 1.5 : null]);
    return Math.max(1, ...vals.filter((v) => v != null));
  }, [cercanas]);
  const masCercana = cercanas[0] ?? null;
  const serie = useMemo(() => {
    if (!masCercana || !filas24.length) return null;
    const cod = codDeEstacion(filas24, masCercana.nombre);
    return cod ? serie24(filas24, cod) : null;
  }, [filas24, masCercana]);
  const noRevisada = !revisada || ahora.error;

  return (
    <section className={cn("px-4 pt-3", className)} aria-label="Lluvia cerca de ti">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        <h3 className="inline-flex items-center gap-1.5 text-[0.68rem] uppercase tracking-wider text-muted-foreground">
          <Droplets className="h-3.5 w-3.5 text-met" aria-hidden="true" />
          Lluvia cerca de ti (SENAMHI)
        </h3>
        {!porGps && <span className="text-[0.68rem] text-muted-foreground">desde el centro de {ciudad}</span>}
      </div>
      {!origen && <p className="mt-1 text-sm text-muted-foreground">Elige tu ciudad o activa tu ubicación.</p>}
      {origen && ahora.datos == null && !ahora.error && <p className="mt-1 text-sm text-muted-foreground">Consultando las estaciones de SENAMHI…</p>}
      {origen && noRevisada && ahora.datos != null && (
        <p className="mt-1 text-sm text-nivel-alerta">No se pudo revisar la lluvia de las estaciones de SENAMHI. Las barras pueden estar atrasadas.</p>
      )}
      {origen && ahora.error && <p className="mt-1 text-sm text-nivel-alerta">No se pudo revisar la lluvia de las estaciones de SENAMHI.</p>}
      {origen && ahora.datos && cercanas.length === 0 && (
        <p className="mt-1 text-sm text-muted-foreground">No hay estaciones de SENAMHI con lluvia de la última hora y referencia que SIMPAC pueda revisar.</p>
      )}
      {cercanas.length > 0 && (
        <>
          {cercanas[0].lejos && (
            <p className="mt-1 text-sm text-muted-foreground">
              No hay estaciones de SENAMHI con lluvia de la última hora a menos de 30 km; la más cercana es {cercanas[0].corto}, a {textoKm(cercanas[0].km)}.
            </p>
          )}
          <ul className={cn("mt-2 grid gap-2", cercanas.length === 1 ? "grid-cols-1" : cercanas.length === 2 ? "grid-cols-2" : "grid-cols-3", ahora.error && "opacity-60 grayscale")}>
            {cercanas.map((e, i) => (
              <BarraHora key={e.nombre} e={e} i={i} montado={montado} max={max} />
            ))}
          </ul>
          {serie && <Serie serie={serie} nombre={masCercana.corto} montado={montado} />}
        </>
      )}
      <p className={cn("mt-1.5 text-[0.66rem] leading-snug", vieja ? "font-medium text-nivel-alerta" : "text-muted-foreground")}>
        {hora ? `Lectura de SENAMHI ${vieja ? "sin actualizar desde " : ""}${horaPeru(hora)} · ` : ""}
        la referencia cambia por lugar; no es un aviso oficial. La línea punteada es la referencia de SENAMHI de cada estación en 1 h.
      </p>
    </section>
  );
}
