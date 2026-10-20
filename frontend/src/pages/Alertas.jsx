import { useEffect, useMemo, useState } from "react";
import { ExternalLink, Megaphone, Waves } from "lucide-react";
import PanelPagina from "@/components/PanelPagina";
import TarjetaAlerta from "@/components/TarjetaAlerta";
import { Cargando, ErrorCarga, Vacio } from "@/components/EstadoCarga";
import { Button } from "@/components/ui/button";
import { useApp } from "@/components/ContextoApp";
import { GRUPOS_TIPO, NIVELES_FILTRO, agruparAvisosVigentes, prepararAlertas, rangoPasadas, textoDiasAviso } from "@/lib/alertas";
import { COLOR_NIVEL, claveAviso, cuando, tituloAviso } from "@/lib/avisoTexto";
import { TITULO_NIVEL, ZONA_HEX, fraseCorta } from "@/lib/zonaRio";
import { fechaPeru, horaPeru, momentoPeru } from "@/lib/tiempo";
import { getAlertasPasadas, getAvisosVigentes } from "@/lib/queries";
import { CITIES } from "@/data/cities";
import { AVISO_ARO } from "@/map/palette";
import { cn } from "@/lib/utils";

const DEPTOS = [...new Set(CITIES.map((c) => c.depto))].sort((a, b) => a.localeCompare(b, "es"));

function Chip({ activo, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={activo}
      className={cn(
        "rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
        activo ? "border-foreground bg-foreground text-background" : "border-border bg-card text-muted-foreground hover:bg-accent hover:text-foreground"
      )}
    >
      {children}
    </button>
  );
}

// Alertas vigentes (vista alerta_actual, la misma del panel de estado), avisos de SENAMHI y ríos
// vigilados de la zona; y la pestaña "Pasadas" (tabla alerta, hasta 30 días).
export default function Alertas() {
  const { p, depto, rios, verRioEnMapa } = useApp();
  const [pestana, setPestana] = useState("ahora");
  const [nivel, setNivel] = useState("todos");
  const [tipo, setTipo] = useState("todos");
  const [zona, setZona] = useState("mia");
  const error = p.alertas == null && (p.sinConexion || /^No se pudo/.test(p.local ?? ""));
  const lista = useMemo(() => (p.alertas ? prepararAlertas(p.alertas, { nivel, tipo, zona, depto }) : []), [p.alertas, nivel, tipo, zona, depto]);

  return (
    <PanelPagina titulo="Alertas y avisos" subtitulo={`Tu zona: ${depto}`} disclaimer>
      <div role="tablist" aria-label="Vigentes o pasadas" className="mb-3 inline-flex rounded-xl border border-border bg-card p-[3px]">
        {[
          ["ahora", "Vigentes"],
          ["pasadas", "Pasadas"],
        ].map(([id, label]) => (
          <button
            key={id}
            role="tab"
            type="button"
            aria-selected={pestana === id}
            onClick={() => setPestana(id)}
            className={cn("rounded-[9px] px-3 py-1.5 text-sm font-semibold", pestana === id ? "bg-foreground text-background" : "text-muted-foreground hover:text-foreground")}
          >
            {label}
          </button>
        ))}
      </div>

      {/* filtros comunes: zona y nivel; el tipo solo en las vigentes */}
      <div className="mb-3 flex flex-wrap gap-1.5">
        <Chip activo={zona === "mia"} onClick={() => setZona("mia")}>
          Mi zona ({depto})
        </Chip>
        <Chip activo={zona === "pais"} onClick={() => setZona("pais")}>
          Todo el país
        </Chip>
      </div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <label className="text-xs text-muted-foreground">
          Nivel{" "}
          <select value={nivel} onChange={(e) => setNivel(e.target.value)} className="rounded-md border border-border bg-background px-2 py-1 text-xs text-foreground">
            {NIVELES_FILTRO.map((n) => (
              <option key={n.id} value={n.id}>
                {n.label}
              </option>
            ))}
          </select>
        </label>
        {pestana === "ahora" && (
          <div className="flex flex-wrap gap-1.5">
            {GRUPOS_TIPO.map((g) => (
              <Chip key={g.id} activo={tipo === g.id} onClick={() => setTipo(g.id)}>
                {g.label}
              </Chip>
            ))}
          </div>
        )}
      </div>

      {pestana === "pasadas" ? (
        <Pasadas zona={zona} depto={depto} nivel={nivel} />
      ) : (
        <>
          <p className="mb-2 text-sm">{p.local}</p>
          {p.alertas == null && !error && <Cargando texto="Consultando las alertas…" />}
          {error && <ErrorCarga texto="No se pudo consultar las alertas. Revisa tu conexión." onReintentar={p.refresh} />}
          {p.alertas != null && lista.length === 0 && (
            <Vacio
              titulo={zona === "mia" ? `No hay alertas ni avisos vigentes en ${depto}${nivel !== "todos" || tipo !== "todos" ? " con esos filtros" : ""}.` : "No hay alertas ni avisos vigentes con esos filtros."}
              texto={`Última revisión · ríos: ${p.actualizado ? horaPeru(p.actualizado) : "sin dato"} · lluvia: ${p.lluviaActualizada ? horaPeru(p.lluviaActualizada) : "sin dato"}.`}
            >
              {zona === "mia" && p.cuantasFuera > 0 && (
                <Button variant="outline" size="sm" className="mt-3" onClick={() => setZona("pais")}>
                  Ver las {p.cuantasFuera} del resto del país
                </Button>
              )}
            </Vacio>
          )}
          <div className="space-y-2">
            {lista.map((a) => (
              <TarjetaAlerta key={`${a.tipo}:${a.referencia}:${a.nivel}:${a.zona}`} a={a} />
            ))}
          </div>
          {p.alertas != null && (
            <p className="mt-2 text-[0.7rem] text-muted-foreground">
              Ríos: {p.actualizado ? `actualizado ${horaPeru(p.actualizado)}` : "sin dato"} (ANA) · lluvia: {p.lluviaActualizada ? `actualizada ${horaPeru(p.lluviaActualizada)}` : "sin dato"} (SENAMHI).
              La lluvia medida no cuenta en el contador de alertas: no es un aviso oficial.
            </p>
          )}

          <AvisosSenamhi zona={zona} depto={depto} />
          <RiosVigilados rios={rios} depto={depto} onVer={verRioEnMapa} />
        </>
      )}
    </PanelPagina>
  );
}

// Avisos de SENAMHI que no han terminado (vista aviso_vigente), uno por aviso con sus días y con
// el nivel más alto de sus áreas (lib/alertas.js agruparAvisosVigentes): el nivel oficial del aviso.
function AvisosSenamhi({ zona, depto }) {
  const [estado, setEstado] = useState({ avisos: null, error: false });
  const cargar = () => {
    setEstado((e) => ({ ...e, error: false }));
    getAvisosVigentes().then(
      (avisos) => setEstado({ avisos, error: false }),
      () => setEstado({ avisos: null, error: true })
    );
  };
  useEffect(cargar, []);
  const hoy = fechaPeru();
  const lista = useMemo(
    () =>
      agruparAvisosVigentes(estado.avisos ?? [])
        .filter((a) => zona !== "mia" || !depto || a.departamentos?.includes(depto))
        .sort((a, b) => b.nivel - a.nivel || a.inicio.localeCompare(b.inicio)),
    [estado.avisos, zona, depto]
  );

  return (
    <section className="mt-6" aria-labelledby="avisos-senamhi">
      <h2 id="avisos-senamhi" className="mb-2 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
        <Megaphone className="h-4 w-4" />
        Avisos de SENAMHI vigentes
      </h2>
      {estado.avisos == null && !estado.error && <Cargando />}
      {estado.error && <ErrorCarga texto="No se pudieron cargar los avisos de SENAMHI." onReintentar={cargar} />}
      {estado.avisos != null && lista.length === 0 && (
        <p className="text-sm text-muted-foreground">
          {zona === "mia" ? `No hay avisos de SENAMHI que cubran ${depto} ahora.` : "No hay avisos de SENAMHI vigentes ahora."}
        </p>
      )}
      <div className="space-y-2">
        {lista.map((a) => {
          const color = COLOR_NIVEL[a.nivel];
          const dias = textoDiasAviso(a, (d) => cuando(d, hoy));
          return (
            <article key={claveAviso(a)} className="rounded-xl border border-border bg-card p-3.5" style={{ boxShadow: `inset 4px 0 0 ${AVISO_ARO[a.nivel] ?? "#9CA3AF"}` }}>
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="font-semibold" style={{ color: AVISO_ARO[a.nivel] }}>
                  Aviso {color} (nivel {a.nivel} de 4)
                </span>
                {a.en_curso ? <span className="text-muted-foreground">en curso</span> : <span className="text-muted-foreground">por empezar</span>}
              </div>
              <h3 className="mt-1 text-sm font-semibold leading-snug">{tituloAviso(a)}</h3>
              <p className="mt-1 text-xs text-muted-foreground">
                Días: {dias} · rige desde {momentoPeru(a.inicio)} hasta {momentoPeru(a.fin)}
              </p>
              {a.departamentos?.length > 0 && <p className="text-xs text-muted-foreground">Cubre: {a.departamentos.join(", ")}</p>}
              <p className="mt-1.5 text-sm leading-snug">{a.texto_dia ?? a.descripcion}</p>
              <p className="mt-2 text-[0.7rem] text-muted-foreground">
                Fuente: SENAMHI (aviso oficial).{" "}
                {a.url && /^https:/.test(a.url) && (
                  <a href={a.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 underline hover:text-foreground">
                    Ver el aviso oficial <ExternalLink className="h-3 w-3" />
                  </a>
                )}
              </p>
            </article>
          );
        })}
      </div>
    </section>
  );
}

// Ríos vigilados de la zona (hoy, el Mashcón en Cajamarca) con el nivel de la zona que podrían afectar.
function RiosVigilados({ rios, depto, onVer }) {
  return (
    <section className="mt-6" aria-labelledby="rios-vigilados">
      <h2 id="rios-vigilados" className="mb-2 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
        <Waves className="h-4 w-4" />
        Ríos vigilados
      </h2>
      {rios.length === 0 && (
        <p className="text-sm text-muted-foreground">
          SIMPAC no tiene todavía un río vigilado con mapa de zonas en {depto}. Por ahora vigila el río Mashcón (Cajamarca).
        </p>
      )}
      <div className="space-y-2">
        {rios.map(({ rio, estado }) => {
          const f = fraseCorta(rio, estado);
          return (
            <article key={rio.id} className="rounded-xl border border-border bg-card p-3.5">
              <div className="flex items-center gap-2">
                <span className="h-3 w-3 rounded-full" style={{ background: ZONA_HEX[estado.nivel] }} />
                <h3 className="text-sm font-semibold">{rio.nombre}</h3>
                <span className="text-xs text-muted-foreground">· {TITULO_NIVEL[estado.nivel]}</span>
              </div>
              <p className="mt-1.5 text-sm leading-snug">
                {f.texto}
                {f.accion ? ` ${f.accion}` : ""}
              </p>
              {estado.senales?.length > 0 && (
                <ul className="mt-1.5 list-disc pl-5 text-xs text-muted-foreground">
                  {estado.senales.slice(0, 3).map((s) => (
                    <li key={s.clave}>{s.texto ?? s.titulo}</li>
                  ))}
                </ul>
              )}
              <p className="mt-1 text-[0.7rem] text-muted-foreground">Fuentes: ANA (estación {rio.estacion_ana}) y avisos de SENAMHI.</p>
              <Button variant="outline" size="sm" className="mt-2" onClick={() => onVer(rio)}>
                Ver en el mapa
              </Button>
            </article>
          );
        })}
      </div>
    </section>
  );
}

// Pestaña "Pasadas": la tabla alerta (lectura pública) con filtro por fechas y zona.
function Pasadas({ zona, depto, nivel }) {
  const hoy = fechaPeru();
  const [fechas, setFechas] = useState(() => rangoPasadas({}, hoy));
  const [zonaLista, setZonaLista] = useState(zona === "mia" ? depto : "");
  useEffect(() => setZonaLista(zona === "mia" ? depto : ""), [zona, depto]);
  const [estado, setEstado] = useState({ filas: null, error: false });
  const cargar = () => {
    setEstado({ filas: null, error: false });
    getAlertasPasadas({ desde: fechas.desde, hasta: fechas.hasta, zona: zonaLista || null }).then(
      (filas) => setEstado({ filas, error: false }),
      () => setEstado({ filas: null, error: true })
    );
  };
  useEffect(cargar, [fechas.desde, fechas.hasta, zonaLista]);
  const lista = useMemo(() => (estado.filas ? prepararAlertas(estado.filas, { nivel }) : []), [estado.filas, nivel]);
  const cambiar = (campo, valor) => setFechas((f) => rangoPasadas({ ...f, [campo]: valor }, hoy));

  return (
    <section aria-label="Alertas pasadas">
      <div className="mb-3 flex flex-wrap items-end gap-2 text-xs">
        <label className="flex flex-col gap-0.5 text-muted-foreground">
          Desde
          <input type="date" value={fechas.desde} max={fechas.hasta} onChange={(e) => cambiar("desde", e.target.value)} className="rounded-md border border-border bg-background px-2 py-1 text-foreground" />
        </label>
        <label className="flex flex-col gap-0.5 text-muted-foreground">
          Hasta
          <input type="date" value={fechas.hasta} max={hoy} onChange={(e) => cambiar("hasta", e.target.value)} className="rounded-md border border-border bg-background px-2 py-1 text-foreground" />
        </label>
        <label className="flex flex-col gap-0.5 text-muted-foreground">
          Zona
          <select value={zonaLista} onChange={(e) => setZonaLista(e.target.value)} className="rounded-md border border-border bg-background px-2 py-1 text-foreground">
            <option value="">Todo el país</option>
            {DEPTOS.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
      </div>
      {fechas.aviso && <p className="mb-2 text-xs text-nivel-alerta">{fechas.aviso}</p>}
      {estado.filas == null && !estado.error && <Cargando texto="Buscando alertas pasadas…" />}
      {estado.error && <ErrorCarga texto="No se pudieron cargar las alertas pasadas." onReintentar={cargar} />}
      {estado.filas != null && lista.length === 0 && (
        <Vacio titulo="No hubo alertas ni avisos en ese rango." texto="Se guardan las de los últimos 30 días. Las alertas de lluvia medida se reemplazan en cada corrida: aquí quedan solo las más recientes." />
      )}
      {estado.filas != null && lista.length > 0 && (
        <p className="mb-2 text-xs text-muted-foreground">
          {lista.length} {lista.length === 1 ? "registro" : "registros"} entre el {fechas.desde.split("-").reverse().join("/")} y el {fechas.hasta.split("-").reverse().join("/")}
          {estado.filas.length >= 500 ? " (se muestran los 500 más recientes)" : ""}.
        </p>
      )}
      <div className="space-y-2">
        {lista.map((a) => (
          <TarjetaAlerta key={`${a.id ?? ""}:${a.tipo}:${a.referencia}:${a.nivel}:${a.ts}`} a={a} />
        ))}
      </div>
    </section>
  );
}
