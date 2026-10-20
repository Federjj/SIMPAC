import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Send } from "lucide-react";
import PanelPagina from "@/components/PanelPagina";
import TarjetaReporte from "@/components/TarjetaReporte";
import { Cargando, EntraPara, ErrorCarga, Mensaje, Vacio } from "@/components/EstadoCarga";
import { Button } from "@/components/ui/button";
import { useApp } from "@/components/ContextoApp";
import { useSesion } from "@/hooks/useSesion";
import { comentar, getComentarios, getMisVotos, getReporte } from "@/lib/queries";
import { MAX_MENSAJE, distanciaKm, hace, mensajeErrorBD, validarTexto, vigente } from "@/lib/comunidad";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Detalle de un reporte: la tarjeta completa, los votos y el hilo de comentarios (lectura
// pública; comentar pide sesión). Si la BD no lo entrega es que venció o no existe.
export default function ReporteDetalle() {
  const { id } = useParams();
  const { userPos, ciudad, irAlMapa } = useApp();
  const { conSesion, cargando: cargandoSesion } = useSesion();
  const [estado, setEstado] = useState({ reporte: undefined, comentarios: [], error: false });
  const [miVoto, setMiVoto] = useState(null);
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [aviso, setAviso] = useState(null);

  const cargar = useCallback(async () => {
    if (!UUID.test(id ?? "")) {
      setEstado({ reporte: null, comentarios: [], error: false });
      return;
    }
    try {
      const [reporte, comentarios] = await Promise.all([getReporte(id), getComentarios(id)]);
      setEstado({ reporte, comentarios, error: false });
      if (reporte && conSesion) setMiVoto((await getMisVotos([id]).catch(() => ({})))[id] ?? null);
    } catch (e) {
      console.error("reporte", e);
      setEstado((s) => ({ ...s, error: true }));
    }
  }, [id, conSesion]);
  useEffect(() => {
    cargar();
  }, [cargar]);

  const enviar = async (e) => {
    e.preventDefault();
    const v = validarTexto(texto, MAX_MENSAJE);
    if (!v.ok) return setAviso(v.error);
    setEnviando(true);
    setAviso(null);
    const { comentario, error } = await comentar(id, v.texto);
    if (error) setAviso(mensajeErrorBD(error, "comentar"));
    else {
      setEstado((s) => ({ ...s, comentarios: [...s.comentarios, comentario] }));
      setTexto("");
    }
    setEnviando(false);
  };

  const r = estado.reporte;
  const pos = userPos ? { lat: userPos[0], lon: userPos[1] } : { lat: ciudad.lat, lon: ciudad.lon };
  return (
    <PanelPagina titulo="Reporte" volver="/comunidad" disclaimer>
      {r === undefined && !estado.error && <Cargando />}
      {estado.error && <ErrorCarga texto="No se pudo cargar el reporte." onReintentar={cargar} />}
      {r === null && <Vacio titulo="Este reporte ya venció o no existe." texto="Los reportes duran 12 horas. Vuelve a la lista para ver los vigentes." />}
      {r && (
        <>
          <TarjetaReporte
            r={{ ...r, distanciaKm: distanciaKm(r, pos) }}
            miVoto={miVoto}
            onCambio={(nuevo, voto) => {
              setEstado((s) => ({ ...s, reporte: { ...s.reporte, ...nuevo } }));
              setMiVoto(voto);
            }}
            onVerMapa={(x) => irAlMapa({ lat: x.lat, lon: x.lon, zoom: 16 })}
            detalle
          />
          <section className="mt-5" aria-labelledby="comentarios">
            <h2 id="comentarios" className="mb-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Comentarios ({estado.comentarios.length})
            </h2>
            {estado.comentarios.length === 0 && <p className="mb-2 text-sm text-muted-foreground">Nadie ha comentado todavía.</p>}
            <ul className="space-y-2">
              {estado.comentarios.map((c) => (
                <li key={c.id} className="rounded-lg border border-border bg-card px-3 py-2">
                  <p className="whitespace-pre-line text-sm leading-snug">{c.texto}</p>
                  <p className="mt-1 text-[0.68rem] text-muted-foreground">Vecino · {hace(c.creado_en)}</p>
                </li>
              ))}
            </ul>
            {!cargandoSesion && !conSesion && <EntraPara que="comentar" compacto className="mt-3" />}
            {conSesion && !vigente(r) && <p className="mt-3 text-sm text-muted-foreground">Este reporte ya venció: no admite comentarios nuevos.</p>}
            {conSesion && vigente(r) && (
              <form onSubmit={enviar} className="mt-3 space-y-2">
                <label className="block text-xs text-muted-foreground">
                  Tu comentario (hasta {MAX_MENSAJE} letras)
                  <textarea
                    value={texto}
                    onChange={(e) => setTexto(e.target.value)}
                    maxLength={MAX_MENSAJE + 50}
                    rows={3}
                    className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                    placeholder="Lo que viste, con respeto. Sin datos personales."
                  />
                </label>
                <div className="flex items-center gap-2">
                  <Button type="submit" size="sm" disabled={enviando}>
                    <Send className="h-4 w-4" />
                    {enviando ? "Enviando…" : "Comentar"}
                  </Button>
                  <span className="text-xs text-muted-foreground">{texto.trim().length}/{MAX_MENSAJE}</span>
                </div>
                <Mensaje>{aviso}</Mensaje>
              </form>
            )}
          </section>
        </>
      )}
    </PanelPagina>
  );
}
