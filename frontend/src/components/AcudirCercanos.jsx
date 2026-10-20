import { useEffect, useState } from "react";
import { Cross, ExternalLink, Flame, MapPin, Mountain, Phone, Shield } from "lucide-react";
import { Cargando, ErrorCarga } from "@/components/EstadoCarga";
import { EMERGENCIAS } from "@/data/emergencias";
import {
  NOTA_MUNICIPALIDAD,
  RADIO_KM,
  TIPO_ACUDIR,
  TIPOS_TARJETA,
  ZONA_SEGURA,
  getPuntosAcudir,
  masCercanos,
  notaFuente,
  telHref,
  telefonos,
  textoDistancia,
  tituloTipo,
} from "@/lib/acudir";
import { cn } from "@/lib/utils";

// "A dónde acudir" cerca de un punto: el establecimiento de salud, la comisaría y la compañía de
// bomberos más cercanos (tabla punto_acudir), con distancia, teléfono y "Ver en el mapa". Arriba,
// los números de emergencia; abajo, la recomendación general de INDECI sobre la zona segura y de
// dónde sale cada dato. Sin lat/lon solo se ven los números.
//   lat, lon      desde dónde se mide (GPS o el centro de la ciudad elegida)
//   desde         opcional: cómo decirlo ("desde el centro de Cajamarca", "desde tu ubicación")
//   compacto      menos texto (para la tarjeta del inicio)
//   onVerEnMapa   ({ lat, lon, clave }) centra el mapa y enciende la capa "acudir"
const ICONO = { salud: Cross, comisaria: Shield, bomberos: Flame };
const URGENTES = ["105", "116", "106"];
const CORTO = { 105: "Policía", 116: "Bomberos", 106: "SAMU" };

function LineaEmergencia() {
  const lista = URGENTES.map((n) => EMERGENCIAS.find((e) => e.numero === n)).filter(Boolean);
  return (
    <p className="text-sm font-semibold leading-snug">
      Si hay emergencia:{" "}
      {lista.map((e, i) => (
        <span key={e.numero}>
          {i > 0 && <span className="text-muted-foreground"> · </span>}
          <a href={telHref(e.numero)} className="underline decoration-dotted underline-offset-2" title={e.nota ? `${e.servicio}. ${e.nota}` : e.servicio}>
            {e.numero}
          </a>{" "}
          <span className="font-normal">{CORTO[e.numero]}</span>
        </span>
      ))}
    </p>
  );
}

// Lista completa de números (cuando no hay desde dónde medir).
function Numeros({ compacto }) {
  const lista = compacto ? EMERGENCIAS.filter((e) => e.ambito === "nacional") : EMERGENCIAS;
  return (
    <ul className="mt-2 divide-y divide-border rounded-xl border border-border bg-card text-sm">
      {lista.map((e) => (
        <li key={`${e.ambito}-${e.numero}`} className="flex items-start gap-2 px-3 py-2">
          <Phone className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          <span className="min-w-0 flex-1">
            <span className="block leading-snug">{e.servicio}</span>
            {e.nota && <span className="block text-xs text-muted-foreground">{e.nota}</span>}
          </span>
          <span className="shrink-0 whitespace-nowrap text-right font-semibold">
            {telefonos(e.numero).map((t, i) => (
              <span key={t}>
                {i > 0 && <br />}
                <a href={telHref(t)} className="underline decoration-dotted underline-offset-2">
                  {t}
                </a>
              </span>
            ))}
          </span>
        </li>
      ))}
    </ul>
  );
}

function Tarjeta({ p, onVerEnMapa, compacto }) {
  const Icono = ICONO[p.tipo] ?? MapPin;
  const tels = telefonos(p.telefono);
  const ver = () => {
    onVerEnMapa?.({ lat: p.lat, lon: p.lon, clave: p.clave });
    // la capa del mapa (map/layers/acudir.js) abre el popup de este punto cuando lo dibuja
    window.dispatchEvent(new CustomEvent("simpac:acudir-ver", { detail: { clave: p.clave } }));
  };
  return (
    <li className="flex items-start gap-2.5 px-3 py-2.5">
      <span className="ac-icono" style={{ background: TIPO_ACUDIR[p.tipo]?.color }} aria-hidden="true">
        <Icono />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-[0.68rem] uppercase tracking-wider text-muted-foreground">
          {tituloTipo(p)}
          {p.atiende_24h === true && <span className="ml-1.5 rounded bg-nivel-normal/15 px-1 py-px normal-case tracking-normal text-green-800">24 h</span>}
        </p>
        <p className="text-sm font-semibold leading-snug">{p.nombre}</p>
        <p className="text-xs text-muted-foreground">
          {textoDistancia(p.distancia_m)}
          {!compacto && p.direccion && <> · {p.direccion}</>}
          {!compacto && !p.direccion && p.distrito && <> · {p.distrito}</>}
        </p>
        <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          {tels.length ? (
            tels.slice(0, 2).map((t) => (
              <a key={t} href={telHref(t)} className="inline-flex items-center gap-1 font-medium underline underline-offset-2">
                <Phone className="h-3 w-3" />
                {t}
              </a>
            ))
          ) : (
            <span className="text-muted-foreground">Sin teléfono en la fuente</span>
          )}
          {onVerEnMapa && (
            <button type="button" onClick={ver} className="inline-flex items-center gap-1 font-medium text-muted-foreground underline hover:text-foreground">
              <MapPin className="h-3 w-3" />
              Ver en el mapa
            </button>
          )}
        </p>
      </div>
    </li>
  );
}

export default function AcudirCercanos({ lat, lon, desde, compacto = false, onVerEnMapa, className }) {
  const hayPunto = lat != null && lon != null;
  const [estado, setEstado] = useState({ cargando: hayPunto, error: null, cercanos: [], vez: 0 });
  const reintentar = () => setEstado((s) => ({ ...s, cargando: true, error: null, vez: s.vez + 1 }));

  useEffect(() => {
    if (!hayPunto) return undefined;
    let vivo = true;
    setEstado((s) => ({ ...s, cargando: true, error: null }));
    getPuntosAcudir({ lat, lon, radioKm: RADIO_KM })
      .then((puntos) => {
        if (!vivo) return;
        const cercanos = masCercanos(puntos, lat, lon, { porTipo: true, maximo: TIPOS_TARJETA.length, maxKm: RADIO_KM }).filter((p) =>
          TIPOS_TARJETA.includes(p.tipo)
        );
        setEstado((s) => ({ ...s, cargando: false, error: null, cercanos }));
      })
      .catch((e) => {
        console.error("acudir", e);
        if (vivo) setEstado((s) => ({ ...s, cargando: false, error: e, cercanos: [] }));
      });
    return () => {
      vivo = false;
    };
  }, [lat, lon, hayPunto, estado.vez]);

  const faltan = TIPOS_TARJETA.filter((t) => !estado.cercanos.some((p) => p.tipo === t));
  const fuentes = [...new Set(estado.cercanos.map((p) => notaFuente(p).replace(/^Fuente: /, "")))];

  return (
    <section className={cn("text-sm", className)} aria-label="A dónde acudir">
      <LineaEmergencia />
      {!hayPunto && (
        <>
          <p className="mt-1 text-xs text-muted-foreground">Elige tu ciudad o activa tu ubicación para ver qué hay cerca de ti.</p>
          <Numeros compacto={compacto} />
        </>
      )}
      {hayPunto && estado.cargando && <Cargando texto="Buscando qué hay cerca…" className="py-3" />}
      {hayPunto && !estado.cargando && estado.error && (
        <ErrorCarga texto="No se pudo cargar lo que hay cerca. Revisa tu conexión." onReintentar={reintentar} className="mt-2" />
      )}
      {hayPunto && !estado.cargando && !estado.error && (
        <>
          {estado.cercanos.length > 0 && (
            <ul className="mt-2 divide-y divide-border rounded-xl border border-border bg-card">
              {estado.cercanos.map((p) => (
                <Tarjeta key={p.clave} p={p} onVerEnMapa={onVerEnMapa} compacto={compacto} />
              ))}
            </ul>
          )}
          {estado.cercanos.length === 0 && (
            <p className="mt-2 rounded-xl border border-dashed border-border px-3 py-2.5 text-sm">
              No tenemos puntos registrados a menos de {RADIO_KM} km; llama al 105 o 116.
            </p>
          )}
          {estado.cercanos.length > 0 && faltan.length > 0 && (
            <p className="mt-1.5 text-xs text-muted-foreground">
              Sin {faltan.map((t) => TIPO_ACUDIR[t].label.toLowerCase()).join(" ni ")} registrados a menos de {RADIO_KM} km.
            </p>
          )}
          <p className="mt-1.5 text-xs text-muted-foreground">
            Distancias en línea recta {desde ?? "desde el punto elegido (tu ubicación o la ciudad)"}.
          </p>
        </>
      )}
      <p className="mt-2 flex items-start gap-1.5 text-xs leading-snug">
        <Mountain className="mt-px h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
        <span>
          <span className="font-semibold">{ZONA_SEGURA.texto}</span>{" "}
          <a
            href={ZONA_SEGURA.url}
            target="_blank"
            rel="noopener noreferrer"
            title={ZONA_SEGURA.detalle}
            className="inline-flex items-center gap-0.5 text-muted-foreground underline decoration-dotted underline-offset-2"
          >
            {compacto ? "INDECI" : ZONA_SEGURA.fuente}
            <ExternalLink className="h-3 w-3" />
          </a>
          {!compacto && <span className="block text-muted-foreground">{NOTA_MUNICIPALIDAD}</span>}
          {compacto && <span className="text-muted-foreground"> {NOTA_MUNICIPALIDAD}</span>}
        </span>
      </p>
      {hayPunto && !compacto && fuentes.length > 0 && (
        <p className="mt-1.5 text-[0.7rem] leading-snug text-muted-foreground">Fuente y hora: {fuentes.join(" ")}</p>
      )}
      {hayPunto && compacto && fuentes.length > 0 && (
        <p className="mt-1 text-[0.68rem] leading-snug text-muted-foreground" title={fuentes.join(" ")}>
          Fuente y hora: SUSALUD RENIPRESS (30-09-2026), MININTER 2019 vía CENEPRED y CGBVP; toca un punto en el mapa para ver la suya.
        </p>
      )}
    </section>
  );
}
