import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Camera, LocateFixed, Send, X } from "lucide-react";
import PanelPagina from "@/components/PanelPagina";
import IconoReporte from "@/components/IconoReporte";
import { Cargando, EntraPara, Mensaje } from "@/components/EstadoCarga";
import { Button } from "@/components/ui/button";
import { useSesion } from "@/hooks/useSesion";
import { useGeolocation } from "@/hooks/useGeolocation";
import { REPORT_TYPES } from "@/lib/reportTypes";
import { crearReporte, subirFotoReporte } from "@/lib/queries";
import { AVISO_REPORTE, MAX_DESCRIPCION, ewkt, mensajeErrorBD, reducirFoto, validarReporte } from "@/lib/comunidad";
import { cn } from "@/lib/utils";

const TEXTO_GPS = {
  pending: "Buscando tu ubicación…",
  denied: "No diste permiso de ubicación. Sin ella no se puede reportar: es la decisión del equipo para evitar reportes falsos (solo se reporta desde donde uno está). Actívala en tu navegador y vuelve a intentar.",
  unavailable: "No se pudo obtener tu ubicación. Revisa que el GPS esté prendido y vuelve a intentar.",
};

// Crear un reporte: solo con sesión y solo con la posición GPS real (sin pin manual). Tipo,
// subtipo si es un atasco, descripción corta y foto opcional (se reduce a 1280 px antes de
// subir). La BD pone autor, confianza, estado y vencimiento, y aplica los límites.
export default function ReporteNuevo() {
  const navigate = useNavigate();
  const { conSesion, cargando, usuario } = useSesion();
  const { pos, status, locate } = useGeolocation();
  const [tipo, setTipo] = useState(null);
  const [subtipo, setSubtipo] = useState(null);
  const [descripcion, setDescripcion] = useState("");
  const [foto, setFoto] = useState(null);
  const [vistaFoto, setVistaFoto] = useState(null);
  const [errores, setErrores] = useState({});
  const [enviando, setEnviando] = useState(null); // null | "foto" | "reporte"
  const [aviso, setAviso] = useState(null);
  const inputFoto = useRef(null);

  useEffect(() => {
    if (conSesion) locate();
  }, [conSesion, locate]);
  useEffect(() => {
    if (!foto) return setVistaFoto(null);
    const url = URL.createObjectURL(foto);
    setVistaFoto(url);
    return () => URL.revokeObjectURL(url);
  }, [foto]);

  const elegirTipo = (id) => {
    setTipo(id);
    setSubtipo(null);
    setErrores((e) => ({ ...e, tipo: undefined, subtipo: undefined }));
  };

  const enviar = async (e) => {
    e.preventDefault();
    const v = validarReporte({ tipo, subtipo, descripcion, pos, foto });
    setErrores(v.errores);
    setAviso(null);
    if (!v.ok) return;
    try {
      let foto_url = null;
      if (foto) {
        setEnviando("foto");
        const chica = await reducirFoto(foto);
        const subida = await subirFotoReporte(chica, usuario.id);
        if (subida.error) {
          setAviso(mensajeErrorBD(subida.error, "subir la foto"));
          setEnviando(null);
          return;
        }
        foto_url = subida.url;
      }
      setEnviando("reporte");
      const { id, error } = await crearReporte({ tipo, subtipo, descripcion: descripcion.trim() || null, foto_url, geom: ewkt(pos[0], pos[1]) });
      if (error || !id) {
        setAviso(mensajeErrorBD(error, "enviar el reporte"));
        setEnviando(null);
        return;
      }
      navigate(`/comunidad/${id}`, { replace: true });
    } catch (err) {
      console.error("reporte nuevo", err);
      setAviso(err?.message === "No se pudo procesar la foto." ? "No se pudo procesar la foto. Prueba con otra o envía el reporte sin foto." : mensajeErrorBD(err, "enviar el reporte"));
      setEnviando(null);
    }
  };

  const t = REPORT_TYPES.find((x) => x.id === tipo);
  const letras = descripcion.trim().length;

  return (
    <PanelPagina titulo="Reportar incidente" volver="/comunidad" disclaimer>
      {cargando && <Cargando />}
      {!cargando && !conSesion && (
        <>
          <EntraPara que="reportar" />
          <p className="mt-3 text-sm text-muted-foreground">
            Los reportes se hacen desde donde estás (ubicación GPS), con el tipo de incidente, una descripción corta y una foto si quieres. Duran 12 horas y la comunidad los vota.
          </p>
        </>
      )}
      {!cargando && conSesion && (
        <form onSubmit={enviar} className="space-y-5">
          <section>
            <h2 className="text-sm font-semibold">Tu ubicación</h2>
            {status === "granted" && pos ? (
              <p className="mt-1 flex items-center gap-1.5 text-sm text-green-800">
                <LocateFixed className="h-4 w-4" />
                Ubicación lista ({pos[0].toFixed(4)}, {pos[1].toFixed(4)}). El reporte se marcará ahí.
              </p>
            ) : (
              <div className="mt-1 text-sm text-muted-foreground">
                <p>{TEXTO_GPS[status] ?? "Se necesita tu ubicación para reportar."}</p>
                {status !== "pending" && (
                  <Button type="button" variant="outline" size="sm" className="mt-2" onClick={locate}>
                    <LocateFixed className="h-4 w-4" />
                    Volver a buscar mi ubicación
                  </Button>
                )}
              </div>
            )}
            {errores.pos && <Mensaje className="mt-2">{errores.pos}</Mensaje>}
          </section>

          <section>
            <h2 className="text-sm font-semibold">¿Qué estás viendo?</h2>
            <div role="radiogroup" aria-label="Tipo de incidente" className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-2 xl:grid-cols-4">
              {REPORT_TYPES.map((x) => (
                <button
                  key={x.id}
                  type="button"
                  role="radio"
                  aria-checked={tipo === x.id}
                  onClick={() => elegirTipo(x.id)}
                  className={cn(
                    "flex items-center gap-2 rounded-xl border px-2.5 py-2 text-left text-xs font-medium transition-colors",
                    tipo === x.id ? "border-foreground bg-foreground text-background" : "border-border bg-card hover:bg-accent"
                  )}
                >
                  <IconoReporte tipo={x.id} tamano="sm" />
                  <span className="leading-tight">{x.label}</span>
                </button>
              ))}
            </div>
            {errores.tipo && <Mensaje className="mt-2">{errores.tipo}</Mensaje>}
            {t?.subtipos && (
              <div className="mt-3">
                <h3 className="text-xs font-semibold text-muted-foreground">¿Qué tan fuerte es el atasco?</h3>
                <div role="radiogroup" aria-label="Intensidad del atasco" className="mt-1.5 flex flex-wrap gap-1.5">
                  {t.subtipos.map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      role="radio"
                      aria-checked={subtipo === s.id}
                      onClick={() => setSubtipo(s.id)}
                      className={cn(
                        "rounded-full border px-3 py-1 text-xs font-medium",
                        subtipo === s.id ? "border-foreground bg-foreground text-background" : "border-border bg-card hover:bg-accent"
                      )}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
                {errores.subtipo && <Mensaje className="mt-2">{errores.subtipo}</Mensaje>}
              </div>
            )}
          </section>

          <section>
            <label className="block text-sm font-semibold" htmlFor="descripcion">
              Cuéntalo en pocas palabras <span className="font-normal text-muted-foreground">(opcional)</span>
            </label>
            <textarea
              id="descripcion"
              value={descripcion}
              onChange={(e) => setDescripcion(e.target.value)}
              rows={3}
              maxLength={MAX_DESCRIPCION + 50}
              placeholder="Ej.: la pista está anegada frente al mercado, pasan solo camionetas."
              className="mt-1.5 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
            />
            <p className={cn("text-xs", letras > MAX_DESCRIPCION ? "text-nivel-emergencia" : "text-muted-foreground")}>
              {letras}/{MAX_DESCRIPCION}
            </p>
            {errores.descripcion && <Mensaje className="mt-1">{errores.descripcion}</Mensaje>}
          </section>

          <section>
            <h2 className="text-sm font-semibold">
              Foto <span className="font-normal text-muted-foreground">(opcional, cámara o galería)</span>
            </h2>
            <input
              ref={inputFoto}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="sr-only"
              onChange={(e) => {
                setFoto(e.target.files?.[0] ?? null);
                setErrores((er) => ({ ...er, foto: undefined }));
              }}
            />
            {vistaFoto ? (
              <div className="mt-2 flex items-start gap-3">
                <img src={vistaFoto} alt="Vista previa de tu foto" className="h-24 w-24 rounded-lg object-cover" />
                <Button type="button" variant="outline" size="sm" onClick={() => setFoto(null)}>
                  <X className="h-4 w-4" />
                  Quitar
                </Button>
              </div>
            ) : (
              <Button type="button" variant="outline" size="sm" className="mt-2" onClick={() => inputFoto.current?.click()}>
                <Camera className="h-4 w-4" />
                Tomar o elegir una foto
              </Button>
            )}
            {errores.foto && <Mensaje className="mt-2">{errores.foto}</Mensaje>}
          </section>

          <p className="rounded-lg bg-muted px-3 py-2 text-xs text-muted-foreground">{AVISO_REPORTE}</p>
          <Mensaje>{aviso}</Mensaje>
          <Button type="submit" variant="destructive" className="w-full" disabled={Boolean(enviando) || status === "pending"}>
            <Send className="h-4 w-4" />
            {enviando === "foto" ? "Subiendo la foto…" : enviando === "reporte" ? "Enviando…" : "Enviar reporte"}
          </Button>
          <p className="text-[0.7rem] text-muted-foreground">
            Máximo 5 reportes por hora. Se publica tu reporte, no tu nombre ni tu correo; la ubicación es la del reporte, no la tuya en el tiempo.
          </p>
        </form>
      )}
    </PanelPagina>
  );
}
