import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Download } from "lucide-react";
import PanelPagina from "@/components/PanelPagina";
import GraficoSerie from "@/components/GraficoSerie";
import { Cargando, ErrorCarga, Vacio } from "@/components/EstadoCarga";
import { Button } from "@/components/ui/button";
import { getCaudales, getEstaciones, getHistoricoCaudal, getHistoricoLluvia, getPrimeraLecturaCaudal, getPrimeraLecturaLluvia } from "@/lib/queries";
import { RANGOS, aCsv, desdeRango, fechaLargaConAnio, horaCorta, instanteCaudal, nombreCsv, resumenCaudal, serieCaudal, serieLluvia, validarParametros } from "@/lib/historico";
import { nombreEstacion, textoRio } from "@/lib/lenguaje";
import { cn } from "@/lib/utils";

const num = (v) => (v == null ? "" : Number(v).toLocaleString("es-PE", { maximumFractionDigits: 2 }));
const sinTildes = (s) => (s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
const FILAS_VISTA = 120;

// Histórico de una estación (/historico?tipo=rio|lluvia&id=...&rio=...&rango=24h|7d|30d): gráfico
// SVG propio, tabla y CSV. Río: lectura_caudal (ANA) con los umbrales de caudal_actual. Lluvia:
// lectura_lluvia (SENAMHI), mm por hora y temperatura si hay.
export default function Historico() {
  const [params, setParams] = useSearchParams();
  const q = useMemo(() => validarParametros(params.toString()), [params]);
  const [estado, setEstado] = useState({ datos: null, error: false, primera: undefined, meta: null });
  const [verTodo, setVerTodo] = useState(false);
  const ahora = useMemo(() => Date.now(), [q.tipo, q.id, q.rio, q.rango]); // eslint-disable-line react-hooks/exhaustive-deps
  const desde = useMemo(() => desdeRango(q.rango, ahora), [q.rango, ahora]);

  const cargar = () => {
    if (!q.ok) return;
    setEstado({ datos: null, error: false, primera: undefined, meta: null });
    setVerTodo(false);
    const pedido =
      q.tipo === "rio"
        ? Promise.all([getHistoricoCaudal({ estacion: q.id, rio: q.rio, desde: desde.fecha }), getCaudales().catch(() => [])]).then(async ([filas, caudales]) => {
            const actual = caudales.find((c) => sinTildes(c.estacion) === sinTildes(q.id) && (!q.rio || sinTildes(c.rio) === sinTildes(q.rio))) ?? null;
            const primera = filas.length ? null : await getPrimeraLecturaCaudal({ estacion: q.id, rio: q.rio }).catch(() => null);
            return { datos: filas, meta: { actual }, primera };
          })
        : Promise.all([getHistoricoLluvia({ cod: q.id, desdeIso: desde.iso }), getEstaciones().catch(() => [])]).then(async ([filas, estaciones]) => {
            const est = estaciones.find((e) => e.cod === q.id) ?? null;
            const primera = filas.length ? null : await getPrimeraLecturaLluvia(q.id).catch(() => null);
            return { datos: filas, meta: { est }, primera };
          });
    pedido.then(
      (r) => setEstado({ ...r, error: false }),
      (e) => {
        console.error("histórico", e);
        setEstado({ datos: null, error: true, primera: undefined, meta: null });
      }
    );
  };
  useEffect(cargar, [q.ok, q.tipo, q.id, q.rio, q.rango]); // eslint-disable-line react-hooks/exhaustive-deps

  const cambiarRango = (r) => {
    const n = new URLSearchParams(params);
    n.set("rango", r);
    setParams(n, { replace: true });
  };

  const titulo = q.tipo === "rio" ? `Histórico: ${q.rio ? `río ${q.rio}` : q.id}` : `Histórico: ${estado.meta?.est ? nombreEstacion(estado.meta.est.nombre) : `estación ${q.id}`}`;
  const subtitulo = q.tipo === "rio" ? `Estación ${q.id} (ANA)` : `Estación ${q.id} (SENAMHI)${estado.meta?.est?.departamento ? ` · ${estado.meta.est.departamento}` : ""}`;

  // series para el gráfico y la tabla
  const rio = q.tipo === "rio" && estado.datos ? serieCaudal(estado.datos, { desdeMs: desde.ms, actual: estado.meta?.actual }) : null;
  const lluvia = q.tipo === "lluvia" && estado.datos ? serieLluvia(estado.datos, { desdeMs: desde.ms }) : null;
  const vacio = estado.datos != null && (rio ? rio.puntos.length === 0 : lluvia.puntos.length === 0);
  const res = rio ? resumenCaudal(rio.puntos) : null;
  const t = rio && estado.meta?.actual ? textoRio(estado.meta.actual) : null;

  const descargar = () => {
    const csv =
      q.tipo === "rio"
        ? aCsv(
            [
              { titulo: "fecha", valor: "fecha" },
              { titulo: "hora", valor: "hora" },
              { titulo: "valor", valor: "valor" },
              { titulo: "unidad", valor: "unidad" },
              { titulo: "umbral_alerta", valor: "umbral_alerta" },
              { titulo: "umbral_emergencia", valor: "umbral_emergencia" },
              { titulo: "tendencia", valor: "tendencia" },
              { titulo: "estado", valor: "estado" },
              { titulo: "fuente", valor: () => "ANA" },
            ],
            estado.datos.filter((f) => instanteCaudal(f) >= desde.ms)
          )
        : aCsv(
            [
              { titulo: "hora_peru", valor: "ts" },
              { titulo: "medido_en", valor: "medido_en" },
              { titulo: "precip_mm", valor: "precip_mm" },
              { titulo: "temp_c", valor: "temp_c" },
              { titulo: "fuente", valor: () => "SENAMHI" },
            ],
            estado.datos.filter((f) => Date.parse(f.medido_en) >= desde.ms)
          );
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = nombreCsv(q.tipo, q.rio ? `${q.rio}_${q.id}` : q.id, q.rango);
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  if (!q.ok) {
    return (
      <PanelPagina titulo="Histórico por estación">
        <Vacio titulo="Falta decir qué estación mirar.">
          <ul className="mt-2 list-disc pl-5 text-left text-sm text-muted-foreground">
            {q.errores.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
          <p className="mt-2 text-sm text-muted-foreground">Entra desde el mapa: toca una estación de río o de lluvia y elige "Ver histórico".</p>
        </Vacio>
      </PanelPagina>
    );
  }

  const filasTabla = rio
    ? [...rio.puntos].reverse()
    : lluvia
      ? [...lluvia.puntos].reverse()
      : [];
  const visibles = verTodo ? filasTabla : filasTabla.slice(0, FILAS_VISTA);

  return (
    <PanelPagina titulo={titulo} subtitulo={subtitulo}>
      <div role="group" aria-label="Rango" className="mb-3 inline-flex rounded-xl border border-border bg-card p-[3px]">
        {RANGOS.map((r) => (
          <button
            key={r.id}
            type="button"
            aria-pressed={q.rango === r.id}
            onClick={() => cambiarRango(r.id)}
            className={cn("rounded-[9px] px-3 py-1.5 text-sm font-semibold", q.rango === r.id ? "bg-foreground text-background" : "text-muted-foreground hover:text-foreground")}
          >
            {r.label}
          </button>
        ))}
      </div>
      {q.avisos.map((a) => (
        <p key={a} className="mb-2 text-xs text-nivel-alerta">
          {a}
        </p>
      ))}
      {estado.datos == null && !estado.error && <Cargando texto="Cargando el histórico…" />}
      {estado.error && <ErrorCarga texto="No se pudo cargar el histórico." onReintentar={cargar} />}
      {vacio && (
        <Vacio
          titulo={`No hay lecturas en ${RANGOS.find((r) => r.id === q.rango)?.label ?? "ese rango"}.`}
          texto={
            estado.primera
              ? `Hay datos desde el ${fechaLargaConAnio(estado.primera.fecha ?? estado.primera.medido_en)}; prueba con un rango más largo o una fecha más reciente.`
              : "SIMPAC todavía no tiene lecturas guardadas de esta estación."
          }
        />
      )}
      {!vacio && rio && (
        <>
          <p className="mb-2 text-sm">
            {t ? `${t.etiqueta}. ${t.frase}` : `Último valor: ${num(res.ultimo.v)} ${rio.unidad ?? ""} (${horaCorta(res.ultimo.t)}).`}
          </p>
          <GraficoSerie
            tipo="rio"
            puntos={rio.puntos}
            umbralAlerta={rio.umbralAlerta}
            umbralEmergencia={rio.umbralEmergencia}
            unidad={rio.unidad ?? ""}
            desdeMs={desde.ms}
            hastaMs={ahora}
            rango={q.rango}
            resumen={`Caudal de la estación ${q.id}: último ${num(res.ultimo.v)}, máximo ${num(res.max.v)}, mínimo ${num(res.min.v)} ${rio.unidad ?? ""} en ${RANGOS.find((r) => r.id === q.rango)?.label}.`}
          />
          <p className="mt-1 text-xs text-muted-foreground">
            Máximo {num(res.max.v)} ({horaCorta(res.max.t)}) · mínimo {num(res.min.v)} ({horaCorta(res.min.t)}) · {rio.puntos.length} lecturas.
            {rio.umbralAlerta == null && " ANA no publica nivel de alerta para esta estación."}
          </p>
        </>
      )}
      {!vacio && lluvia && (
        <>
          <p className="mb-2 text-sm">
            En {RANGOS.find((r) => r.id === q.rango)?.label} cayeron {num(Math.round(lluvia.totalMm * 10) / 10)} mm en total; la hora con más lluvia tuvo {num(lluvia.maxMm)} mm.
            {lluvia.horasConDato < lluvia.puntos.length && ` ${lluvia.puntos.length - lluvia.horasConDato} horas sin dato de lluvia.`}
          </p>
          <GraficoSerie
            tipo="lluvia"
            puntos={lluvia.puntos}
            desdeMs={desde.ms}
            hastaMs={ahora}
            rango={q.rango}
            resumen={`Lluvia por hora de la estación ${q.id}: ${num(lluvia.totalMm)} mm en total, máximo ${num(lluvia.maxMm)} mm en una hora.`}
          />
        </>
      )}
      {!vacio && estado.datos != null && (
        <>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button variant="outline" size="sm" onClick={descargar}>
              <Download className="h-4 w-4" />
              Descargar CSV
            </Button>
            <span className="text-xs text-muted-foreground">Fuente: {q.tipo === "rio" ? "ANA" : "SENAMHI"} · horas de Perú · guardado por SIMPAC.</span>
          </div>
          <table className="mt-3 w-full text-left text-xs">
            <caption className="sr-only">Lecturas del rango elegido, de la más nueva a la más vieja</caption>
            <thead className="text-muted-foreground">
              <tr className="border-b border-border">
                <th className="py-1 pr-2 font-medium">Hora</th>
                {rio ? (
                  <>
                    <th className="py-1 pr-2 font-medium">{rio.unidad ?? "Valor"}</th>
                    <th className="py-1 font-medium">Estado</th>
                  </>
                ) : (
                  <>
                    <th className="py-1 pr-2 font-medium">mm</th>
                    <th className="py-1 font-medium">°C</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {visibles.map((p) => (
                <tr key={p.t} className="border-b border-border/60">
                  <td className="py-1 pr-2 tabular-nums">{horaCorta(p.t)}</td>
                  {rio ? (
                    <>
                      <td className="py-1 pr-2 tabular-nums">{num(p.v)}</td>
                      <td className="py-1 text-muted-foreground">{p.estado ?? ""}</td>
                    </>
                  ) : (
                    <>
                      <td className="py-1 pr-2 tabular-nums">{p.mm == null ? "sin dato" : num(p.mm)}</td>
                      <td className="py-1 tabular-nums">{p.temp == null ? "" : num(p.temp)}</td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
          {filasTabla.length > FILAS_VISTA && !verTodo && (
            <Button variant="ghost" size="sm" className="mt-2" onClick={() => setVerTodo(true)}>
              Mostrar las {filasTabla.length} lecturas
            </Button>
          )}
        </>
      )}
    </PanelPagina>
  );
}
