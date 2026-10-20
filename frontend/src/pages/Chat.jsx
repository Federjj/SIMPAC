import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { EyeOff, Send } from "lucide-react";
import PanelPagina from "@/components/PanelPagina";
import { Cargando, EntraPara, ErrorCarga, Mensaje } from "@/components/EstadoCarga";
import { Button } from "@/components/ui/button";
import { useApp } from "@/components/ContextoApp";
import { useSesion } from "@/hooks/useSesion";
import { enviarMensaje, escucharMensajes, getMensajes } from "@/lib/queries";
import { MAX_MENSAJE, NORMAS_CHAT, groserias, hace, mensajeErrorBD, mensajesVisibles, validarTexto, venceEn } from "@/lib/comunidad";
import { cn } from "@/lib/utils";

const SONDEO_MS = 10_000;
const CLAVE_OCULTOS = "simpac.chat.ocultos";
const leerOcultos = () => {
  try {
    return new Set(JSON.parse(sessionStorage.getItem(CLAVE_OCULTOS) ?? "[]"));
  } catch {
    return new Set();
  }
};

// Chat por zona: el canal es el departamento de la persona (GPS o ciudad elegida). Solo con
// sesión (la BD no entrega mensajes a quien no la tiene). Mensajes de 2 horas, en tiempo real
// (publicación supabase_realtime) y con sondeo cada 10 s por si el canal se cae o para sacar los
// vencidos. Autocontrol: aviso local de groserías antes de enviar y "ocultar" en este navegador.
export default function Chat() {
  const { depto } = useApp();
  const { conSesion, cargando, usuario } = useSesion();
  const zona = depto;
  const [estado, setEstado] = useState({ mensajes: null, error: false });
  const [ocultos, setOcultos] = useState(leerOcultos);
  const [texto, setTexto] = useState("");
  const [confirmar, setConfirmar] = useState(null); // palabras ofensivas detectadas, a confirmar
  const [enviando, setEnviando] = useState(false);
  const [aviso, setAviso] = useState(null);
  const [tic, setTic] = useState(0); // para refrescar "vence en" cada 30 s
  const fin = useRef(null);

  const cargar = useCallback(async () => {
    try {
      const mensajes = await getMensajes(zona);
      setEstado({ mensajes, error: false });
    } catch (e) {
      console.error("chat", e);
      setEstado((s) => ({ mensajes: s.mensajes, error: true }));
    }
  }, [zona]);

  useEffect(() => {
    if (!conSesion) return undefined;
    setEstado({ mensajes: null, error: false });
    cargar();
    const sondeo = setInterval(cargar, SONDEO_MS);
    const cerrar = escucharMensajes(zona, (m) => setEstado((s) => (s.mensajes?.some((x) => x.id === m.id) ? s : { ...s, mensajes: [...(s.mensajes ?? []), m] })));
    const reloj = setInterval(() => setTic((t) => t + 1), 30_000);
    return () => {
      clearInterval(sondeo);
      clearInterval(reloj);
      cerrar();
    };
  }, [conSesion, zona, cargar]);

  const visibles = useMemo(() => mensajesVisibles(estado.mensajes ?? [], ocultos), [estado.mensajes, ocultos, tic]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    fin.current?.scrollIntoView({ block: "end" });
  }, [visibles.length]);

  const ocultar = (id) => {
    const n = new Set(ocultos);
    n.add(id);
    setOcultos(n);
    try {
      sessionStorage.setItem(CLAVE_OCULTOS, JSON.stringify([...n]));
    } catch {
      /* sin almacenamiento: solo en memoria */
    }
  };

  const enviar = async (e, forzar = false) => {
    e?.preventDefault();
    const v = validarTexto(texto, MAX_MENSAJE);
    if (!v.ok) return setAviso(v.error);
    const malas = groserias(v.texto);
    if (malas.length && !forzar) {
      setConfirmar(malas);
      return;
    }
    setConfirmar(null);
    setEnviando(true);
    setAviso(null);
    const { mensaje, error } = await enviarMensaje(zona, v.texto);
    if (error) setAviso(mensajeErrorBD(error, "enviar el mensaje"));
    else {
      setEstado((s) => (s.mensajes?.some((x) => x.id === mensaje.id) ? s : { ...s, mensajes: [...(s.mensajes ?? []), mensaje] }));
      setTexto("");
    }
    setEnviando(false);
  };

  return (
    <PanelPagina titulo={`Chat de ${zona}`} subtitulo="Canal por zona para lo que está pasando ahora." disclaimer className="flex flex-col">
      <p className="mb-3 rounded-lg bg-muted px-3 py-2 text-xs text-muted-foreground">{NORMAS_CHAT}</p>
      {cargando && <Cargando />}
      {!cargando && !conSesion && (
        <>
          <div className="mb-3 rounded-xl border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
            El canal de {zona} se ve al entrar. Los mensajes duran 2 horas.
          </div>
          <EntraPara que="chatear" />
          <p className="mt-3 text-sm">
            Emergencias: <span className="font-semibold text-nivel-alerta">105 (Policía) · 116 (Bomberos)</span>
          </p>
        </>
      )}
      {!cargando && conSesion && (
        <>
          <div className="min-h-0 flex-1 space-y-2" role="log" aria-live="polite" aria-label={`Mensajes del chat de ${zona}`}>
            {estado.mensajes == null && !estado.error && <Cargando texto="Cargando los mensajes…" />}
            {estado.error && <ErrorCarga texto="No se pudieron cargar los mensajes." onReintentar={cargar} />}
            {estado.mensajes != null && visibles.length === 0 && (
              <p className="rounded-xl border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">
                Nadie ha escrito en {zona} en las últimas 2 horas. Si ves algo, cuéntalo.
              </p>
            )}
            {visibles.map((m) => {
              const mio = m.autor === usuario?.id;
              return (
                <div key={m.id} className={cn("flex", mio ? "justify-end" : "justify-start")}>
                  <div className={cn("max-w-[85%] rounded-2xl px-3 py-2 text-sm", mio ? "bg-primary text-primary-foreground" : "border border-border bg-card")}>
                    <p className="whitespace-pre-line break-words leading-snug">{m.contenido}</p>
                    <p className={cn("mt-1 flex flex-wrap items-center gap-x-2 text-[0.66rem]", mio ? "text-primary-foreground/70" : "text-muted-foreground")}>
                      <span>{mio ? "Tú" : "Vecino"}</span>
                      <span>· {hace(m.creado_en)}</span>
                      <span>· {venceEn(m.expira_en)}</span>
                      {!mio && (
                        <button type="button" onClick={() => ocultar(m.id)} className="inline-flex items-center gap-1 underline" aria-label="Ocultar este mensaje en este navegador">
                          <EyeOff className="h-3 w-3" />
                          Ocultar
                        </button>
                      )}
                    </p>
                  </div>
                </div>
              );
            })}
            <div ref={fin} />
          </div>
          <form onSubmit={enviar} className="sticky bottom-0 mt-3 space-y-2 border-t border-border bg-background pt-3">
            {confirmar && (
              <div role="alertdialog" aria-label="Palabras ofensivas" className="rounded-lg border border-nivel-alerta/60 bg-nivel-alerta/10 px-3 py-2 text-sm">
                <p>
                  Tu mensaje tiene palabras ofensivas ({confirmar.join(", ")}). Este chat es para avisar lo que pasa, con respeto. ¿Quieres editarlo?
                </p>
                <div className="mt-2 flex gap-2">
                  <Button type="button" size="sm" onClick={() => setConfirmar(null)}>
                    Editar
                  </Button>
                  <Button type="button" size="sm" variant="outline" onClick={(e) => enviar(e, true)}>
                    Enviar igual
                  </Button>
                </div>
              </div>
            )}
            <div className="flex items-end gap-2">
              <textarea
                value={texto}
                onChange={(e) => setTexto(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) enviar(e);
                }}
                rows={2}
                maxLength={MAX_MENSAJE + 50}
                aria-label="Tu mensaje"
                placeholder={`Escribe a ${zona}… (Enter envía, Shift+Enter salta de línea)`}
                className="min-h-[2.5rem] flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
              />
              <Button type="submit" size="icon" disabled={enviando} aria-label="Enviar mensaje">
                <Send className="h-4 w-4" />
              </Button>
            </div>
            <div className="flex items-center justify-between text-[0.68rem] text-muted-foreground">
              <span>{texto.trim().length}/{MAX_MENSAJE} · máximo 30 mensajes por hora</span>
              <span>Emergencias: 105 · 116</span>
            </div>
            <Mensaje>{aviso}</Mensaje>
          </form>
        </>
      )}
    </PanelPagina>
  );
}
