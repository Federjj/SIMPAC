import { Circle, LocateFixed, MapPin, Minus, OctagonAlert, Phone, TriangleAlert, Waves } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useContador } from "@/hooks/useContador";
import { ETIQUETA_NIVEL, PIE_OFICIAL, TELEFONOS, textoMetros } from "@/lib/zonaAhora";
import { FRASES_RIO_PAIS } from "@/lib/lenguaje";

// "Tu zona ahora": lo que se lee en 5 segundos al abrir la app. De arriba abajo: 1 el semáforo
// (color + ícono + etiqueta, nunca solo color), 2 el titular corto (lib/zonaAhora.js titularCorto),
// 3 los chips de distancia al río más cercano (el vigilado o uno del país con trazo de ANA) y a la
// zona que podría inundarse (o que no tiene mapa de zonas), 4 el botón según el nivel. En alerta o emergencia se suma UNA instrucción grande y los botones de llamada (105/116).
// Todo texto trae fuente y hora (línea de 0,7 rem); sin GPS se mide desde el centro de la ciudad.
//   zona      lo que devuelve hooks/useZonaAhora.js
//   depto     nombre del departamento (para los textos de degradación)
//   gps       { status, geolocate }  (hooks/useGeolocation)
//   plegado   la hoja está en su altura mínima (celular): solo semáforo, titular, instrucción,
//             fuente y hora y el botón; los chips, el texto del GPS y el pie salen al abrirla
//   onAccion  (accion: "zona"|"pasar"|"acudir"|"avisos") -> Mapa decide qué hace el mapa
//   onVerRio  (rio) -> "Ver en el mapa" del río más cercano (zona.verRio: para un río del país,
//             encuadra a la persona y el tramo más cercano del cauce)
const ICONO = { normal: Circle, aviso: TriangleAlert, alerta: TriangleAlert, emergencia: OctagonAlert, sin_dato: Minus };

function Semaforo({ nivel, etiqueta }) {
  const Icono = ICONO[nivel] ?? Minus;
  return (
    <div className="flex w-16 shrink-0 flex-col items-center gap-1 lg:w-[72px]">
      {/* key: al cambiar de nivel el disco se vuelve a montar y hace un solo "respiro" */}
      <div key={nivel} className="tz-disco" aria-hidden="true">
        <Icono fill={nivel === "normal" ? "currentColor" : "none"} strokeWidth={nivel === "normal" ? 0 : 2.4} />
      </div>
      <span className="tz-etiqueta tz-tinta text-center">{etiqueta ?? ETIQUETA_NIVEL[nivel]}</span>
    </div>
  );
}

// Los metros cuentan de 0 al valor en 700 ms (requestAnimationFrame; con menos movimiento aparece
// el valor final). Para kilómetros se cuenta igual, sobre los metros, y se formatea al final.
function Metros({ metros }) {
  const m = useContador(metros, { dur: 700 });
  return <span className="tz-num">{textoMetros(m)}</span>;
}

function Chip({ chip, i }) {
  const conNivel = chip.nivel ? `tz-${chip.nivel}` : null;
  // punteado: "este río no tiene mapa de zonas" (no afirma nada del nivel)
  if (chip.punteado)
    return (
      <li className="tz-chip inline-flex max-w-full items-center gap-1.5 rounded-full border border-dashed border-border px-2.5 py-1 text-[0.8rem] leading-tight text-muted-foreground" style={{ "--i": i }}>
        <MapPin className="h-3.5 w-3.5 shrink-0" />
        <span className="min-w-0">{chip.texto}</span>
      </li>
    );
  return (
    <li
      className={cn(
        "tz-chip inline-flex max-w-full items-center gap-1.5 rounded-full border px-2.5 py-1 text-[0.8rem] font-medium leading-tight",
        conNivel,
        chip.dentro ? "tz-relleno border-transparent" : chip.nivel ? "tz-suave tz-tinta border-transparent" : "border-border bg-card text-foreground"
      )}
      style={{ "--i": i }}
    >
      {chip.clave === "rio" ? <Waves className="h-3.5 w-3.5 shrink-0" /> : <MapPin className="h-3.5 w-3.5 shrink-0" />}
      <span className="min-w-0">
        {chip.metros != null && chip.antes != null ? (
          <>
            {chip.antes}
            <Metros metros={chip.metros} />
            {chip.despues}
          </>
        ) : (
          chip.texto
        )}
      </span>
    </li>
  );
}

export default function TuZona({ zona, depto, gps, plegado = false, onAccion, onVerRio, className }) {
  const { nivel, titular, instruccion, chips, boton, fuentes, cercano, verRio, porGps, hayRios, hayTrazadosDepto, fuerte, origen } = zona;
  const sinGps = !porGps;
  const gpsPidiendo = gps?.status === "pending";
  const gpsNoDisponible = gps?.status === "denied" || gps?.status === "unavailable";

  return (
    <section className={cn("px-4 pt-3", className)} aria-label="Tu zona ahora">
      <div className="flex items-start gap-3">
        <Semaforo nivel={nivel} etiqueta={titular.etiqueta} />
        <div className="min-w-0 flex-1">
          {/* el titular es lo que lee un lector de pantalla cuando cambia el nivel */}
          <h2 className="tz-titular" aria-live="polite">
            {titular.texto}
          </h2>
          {instruccion && fuerte && <p className="mt-1.5 text-lg font-bold leading-snug">{instruccion}</p>}
          {titular.interpretado && (
            <p className="mt-0.5 text-[0.66rem] text-muted-foreground">
              Resumen {titular.interpretado === "llm" ? "redactado automáticamente con las cifras oficiales" : "del servidor de SIMPAC"}; el nivel lo calcula SIMPAC con los datos de ANA y SENAMHI.
            </p>
          )}
        </div>
      </div>

      {/* chips: dónde estás respecto del río más cercano (vigilado o con trazo de ANA) y de su zona, o
          que no tiene mapa de zonas (lib/zonaAhora.js chipsDistancia y chipSinZonas); sin GPS, cómo
          activarlo. "No vigila ríos" solo si el departamento no tiene ningún río con trazo ni vigilado
          (plegada, la hoja los guarda para cuando se abra: el mapa tiene que verse) */}
      {!plegado && (
        <ul className="mt-2.5 flex flex-wrap gap-1.5" aria-label="Dónde estás">
          {chips.map((c, i) => (
            <Chip key={c.clave} chip={c} i={i} />
          ))}
          {!hayRios && !hayTrazadosDepto && !cercano && zona.nivel !== "sin_dato" && (
            <li className="tz-chip inline-flex items-center gap-1.5 rounded-full border border-dashed border-border px-2.5 py-1 text-[0.8rem] leading-tight text-muted-foreground">
              <Waves className="h-3.5 w-3.5 shrink-0" />
              {FRASES_RIO_PAIS.sinRiosDepto}
            </li>
          )}
        </ul>
      )}
      {!plegado && sinGps && hayRios && (
        <div className="tz-chip mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.8rem] text-muted-foreground" style={{ "--i": 2 }}>
          <span className="inline-flex items-center gap-1.5">
            <LocateFixed className="h-3.5 w-3.5 shrink-0" />
            {gpsNoDisponible
              ? "No pudimos usar tu ubicación: las distancias van desde el centro de la ciudad."
              : "Activa tu ubicación para ver a qué distancia estás tú del río."}
          </span>
          {gps?.geolocate && !gpsNoDisponible && (
            <button type="button" onClick={gps.geolocate} disabled={gpsPidiendo} className="font-medium text-foreground underline underline-offset-2 disabled:opacity-60">
              {gpsPidiendo ? "Buscando tu ubicación…" : "Usar mi ubicación"}
            </button>
          )}
        </div>
      )}

      {/* fuente y hora de cada cosa que se afirma arriba */}
      <p className="mt-2 text-[0.7rem] leading-snug text-muted-foreground">
        {fuentes.map((f, i) => (
          <span key={f.texto}>
            {i > 0 && " · "}
            <span className={cn(f.mal && "font-medium text-nivel-alerta")}>{f.texto}</span>
          </span>
        ))}
        {cercano && verRio && onVerRio && (
          <>
            {" · "}
            <button type="button" onClick={() => onVerRio(verRio)} className="underline hover:text-foreground">
              Ver el {cercano.rio.nombre.replace(/^R[ií]o /, "río ")} en el mapa
            </button>
          </>
        )}
      </p>

      {/* el botón del nivel y, en alerta o emergencia, las llamadas */}
      <div className={cn("mt-2.5 flex gap-2", fuerte ? "flex-wrap" : "")}>
        <Button
          className={cn("h-10 flex-1 text-[0.95rem] font-semibold", `tz-${nivel}`, fuerte ? "tz-relleno shadow" : "")}
          variant={fuerte ? "ghost" : "default"}
          disabled={!origen && boton.accion !== "avisos"}
          onClick={() => onAccion?.(boton.accion)}
        >
          {boton.texto}
        </Button>
        {fuerte &&
          TELEFONOS.map((t) => (
            <Button key={t.numero} asChild variant="outline" className="h-10 px-3 font-semibold">
              <a href={`tel:${t.numero}`} aria-label={`Llamar al ${t.numero}, ${t.quien}`}>
                <Phone className="h-4 w-4" />
                {t.numero}
              </a>
            </Button>
          ))}
      </div>
      {/* plegada no lleva pie: en alerta o emergencia los teléfonos están arriba y la instrucción ya
          manda a Defensa Civil; el texto completo sale al abrir la hoja */}
      {!plegado && (
        <p className="mt-1.5 text-[0.66rem] leading-snug text-muted-foreground">
          {fuerte ? PIE_OFICIAL : `Información referencial; no reemplaza los canales oficiales (105 / 116). Zona: ${depto}.`}
        </p>
      )}
    </section>
  );
}
