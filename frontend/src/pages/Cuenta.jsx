import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { LogOut, MailCheck, Pencil, UserRound } from "lucide-react";
import PanelPagina from "@/components/PanelPagina";
import CitySelector from "@/components/CitySelector";
import { Cargando, ErrorCarga, Mensaje } from "@/components/EstadoCarga";
import { SUBTITULO_SIFEC } from "@/components/Sidebar";
import { Button } from "@/components/ui/button";
import { useApp } from "@/components/ContextoApp";
import { useSesion } from "@/hooks/useSesion";
import { cambiarContrasena, entrar, guardarNombre, guardarZona, guardarZonaLocal, misReportes, pedirNuevaContrasena, registrar, salir } from "@/lib/sesion";
import { ESTADO_REPORTE, POR_QUE_CUENTA, hace, nombreReporte, validarCuenta, vigente } from "@/lib/comunidad";
import { cn } from "@/lib/utils";

const CAMPO = "mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground";

function Campo({ id, label, error, ...props }) {
  return (
    <label htmlFor={id} className="block text-sm">
      {label}
      <input id={id} className={cn(CAMPO, error && "border-nivel-emergencia")} aria-invalid={Boolean(error)} aria-describedby={error ? `${id}-err` : undefined} {...props} />
      {error && (
        <span id={`${id}-err`} className="mt-1 block text-xs text-nivel-emergencia">
          {error}
        </span>
      )}
    </label>
  );
}

// Cuenta: sin sesión, Entrar / Crear cuenta / Olvidé mi contraseña (/cuenta, /cuenta/entrar,
// /cuenta/registro); con sesión, el perfil (nombre, correo, reputación), "Mi zona", "Mis reportes"
// y cerrar sesión. Solo se piden correo, contraseña y un nombre para mostrar.
export default function Cuenta() {
  const { conSesion, cargando, recuperacion } = useSesion();
  return (
    <PanelPagina titulo="Cuenta" subtitulo={SUBTITULO_SIFEC}>
      {cargando && <Cargando texto="Revisando tu sesión…" />}
      {!cargando && recuperacion && <NuevaContrasena />}
      {!cargando && !recuperacion && (conSesion ? <Perfil /> : <Acceso />)}
    </PanelPagina>
  );
}

function Acceso() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const registro = pathname.endsWith("/registro");
  const [modo, setModo] = useState("formulario"); // formulario | recuperar | confirmar
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [nombre, setNombre] = useState("");
  const [errores, setErrores] = useState({});
  const [aviso, setAviso] = useState(null);
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState(null);
  useEffect(() => {
    setErrores({});
    setAviso(null);
  }, [registro, modo]);

  const enviar = async (e) => {
    e.preventDefault();
    setAviso(null);
    if (modo === "recuperar") {
      const v = validarCuenta({ email, password: "xxxxxx" });
      setErrores(v.errores);
      if (!v.ok) return;
      setEnviando(true);
      const r = await pedirNuevaContrasena(email);
      setEnviando(false);
      if (!r.ok) return setAviso({ tipo: "error", texto: r.error });
      setResultado({ titulo: "Revisa tu correo", texto: `Si ${email.trim()} tiene una cuenta, le enviamos un enlace para elegir una contraseña nueva. Revisa también la carpeta de spam.` });
      setModo("confirmar");
      return;
    }
    const v = validarCuenta({ email, password, nombre, conNombre: registro });
    setErrores(v.errores);
    if (!v.ok) return;
    setEnviando(true);
    const r = registro ? await registrar({ email, password, nombre }) : await entrar({ email, password });
    setEnviando(false);
    if (!r.ok) return setAviso({ tipo: "error", texto: r.error });
    if (registro) {
      setResultado({
        titulo: "Revisa tu correo",
        texto: r.yaExistia
          ? `Si ${email.trim()} ya tenía una cuenta, no se crea otra: entra con tu contraseña o pide una nueva. Si no la tenía, te enviamos un enlace para confirmarla.`
          : `Te enviamos un enlace a ${email.trim()} para confirmar tu cuenta. Hasta que lo abras no podrás entrar. Revisa también la carpeta de spam.`,
      });
      setModo("confirmar");
    } else {
      navigate("/cuenta", { replace: true });
    }
  };

  if (modo === "confirmar" && resultado) {
    return (
      <div className="rounded-xl border border-border bg-card p-4">
        <MailCheck className="mb-2 h-7 w-7 text-green-700" />
        <h2 className="text-base font-semibold">{resultado.titulo}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{resultado.texto}</p>
        <Button variant="outline" size="sm" className="mt-3" onClick={() => setModo("formulario")}>
          Volver a entrar
        </Button>
      </div>
    );
  }

  return (
    <div>
      <p className="mb-4 rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground">{POR_QUE_CUENTA}</p>
      {modo === "recuperar" ? (
        <form onSubmit={enviar} className="space-y-3" aria-label="Recuperar contraseña">
          <h2 className="text-base font-semibold">Olvidé mi contraseña</h2>
          <p className="text-sm text-muted-foreground">Te enviamos un enlace por correo para elegir una nueva.</p>
          <Campo id="email-rec" label="Correo" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} error={errores.email} />
          <Mensaje tipo={aviso?.tipo}>{aviso?.texto}</Mensaje>
          <div className="flex gap-2">
            <Button type="submit" disabled={enviando}>
              {enviando ? "Enviando…" : "Enviar enlace"}
            </Button>
            <Button type="button" variant="ghost" onClick={() => setModo("formulario")}>
              Cancelar
            </Button>
          </div>
        </form>
      ) : (
        <>
          <div role="tablist" aria-label="Entrar o crear cuenta" className="mb-4 grid grid-cols-2 rounded-xl border border-border bg-card p-[3px]">
            <Link to="/cuenta/entrar" role="tab" aria-selected={!registro} className={cn("rounded-[9px] px-3 py-1.5 text-center text-sm font-semibold", !registro ? "bg-foreground text-background" : "text-muted-foreground")}>
              Entrar
            </Link>
            <Link to="/cuenta/registro" role="tab" aria-selected={registro} className={cn("rounded-[9px] px-3 py-1.5 text-center text-sm font-semibold", registro ? "bg-foreground text-background" : "text-muted-foreground")}>
              Crear cuenta
            </Link>
          </div>
          <form onSubmit={enviar} className="space-y-3" aria-label={registro ? "Crear cuenta" : "Entrar"}>
            {registro && (
              <Campo id="nombre" label="Nombre para mostrar" type="text" autoComplete="nickname" maxLength={80} value={nombre} onChange={(e) => setNombre(e.target.value)} error={errores.nombre} placeholder="Ej.: Rosa de Baños del Inca" />
            )}
            <Campo id="email" label="Correo" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} error={errores.email} />
            <Campo id="password" label="Contraseña" type="password" autoComplete={registro ? "new-password" : "current-password"} value={password} onChange={(e) => setPassword(e.target.value)} error={errores.password} placeholder={registro ? "Al menos 6 caracteres" : undefined} />
            <Mensaje tipo={aviso?.tipo}>{aviso?.texto}</Mensaje>
            <Button type="submit" className="w-full" disabled={enviando}>
              {enviando ? "Un momento…" : registro ? "Crear cuenta" : "Entrar"}
            </Button>
            {!registro && (
              <button type="button" onClick={() => setModo("recuperar")} className="text-sm text-muted-foreground underline hover:text-foreground">
                Olvidé mi contraseña
              </button>
            )}
            {registro && <p className="text-xs text-muted-foreground">Después de crear la cuenta te llegará un correo para confirmarla. No guardamos más datos que tu correo y ese nombre.</p>}
          </form>
        </>
      )}
    </div>
  );
}

function NuevaContrasena() {
  const { terminarRecuperacion } = useSesion();
  const [password, setPassword] = useState("");
  const [aviso, setAviso] = useState(null);
  const [enviando, setEnviando] = useState(false);
  const enviar = async (e) => {
    e.preventDefault();
    if (password.length < 6) return setAviso({ tipo: "error", texto: "La contraseña tiene que tener al menos 6 caracteres." });
    setEnviando(true);
    const r = await cambiarContrasena(password);
    setEnviando(false);
    if (!r.ok) return setAviso({ tipo: "error", texto: r.error });
    setAviso({ tipo: "ok", texto: "Listo: tu contraseña cambió y ya estás dentro." });
    setTimeout(terminarRecuperacion, 1500);
  };
  return (
    <form onSubmit={enviar} className="space-y-3" aria-label="Contraseña nueva">
      <h2 className="text-base font-semibold">Elige una contraseña nueva</h2>
      <Campo id="password-nueva" label="Contraseña nueva" type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Al menos 6 caracteres" />
      <Mensaje tipo={aviso?.tipo}>{aviso?.texto}</Mensaje>
      <Button type="submit" disabled={enviando}>
        {enviando ? "Guardando…" : "Guardar contraseña"}
      </Button>
    </form>
  );
}

function Perfil() {
  const { usuario, perfil, nombre, recargarPerfil } = useSesion();
  const { city, pickCity } = useApp();
  const navigate = useNavigate();
  const [editando, setEditando] = useState(false);
  const [nuevoNombre, setNuevoNombre] = useState("");
  const [aviso, setAviso] = useState(null);
  const [reportes, setReportes] = useState({ lista: null, error: null });
  const [saliendo, setSaliendo] = useState(false);

  const cargarReportes = () => misReportes().then((r) => setReportes(r.ok ? { lista: r.reportes, error: null } : { lista: null, error: r.error }));
  useEffect(() => {
    cargarReportes();
  }, []);

  const elegirZona = async (nombreCiudad) => {
    pickCity(nombreCiudad);
    guardarZonaLocal(nombreCiudad);
    const r = await guardarZona(nombreCiudad);
    setAviso(r.ok ? { tipo: "ok", texto: `Tu zona ahora es ${nombreCiudad}: el mapa y las alertas arrancan ahí.` } : { tipo: "error", texto: r.error });
    if (r.ok) recargarPerfil();
  };
  const guardar = async (e) => {
    e.preventDefault();
    const r = await guardarNombre(nuevoNombre);
    setAviso(r.ok ? { tipo: "ok", texto: "Nombre guardado." } : { tipo: "error", texto: r.error });
    if (r.ok) {
      setEditando(false);
      recargarPerfil();
    }
  };
  const cerrar = async () => {
    setSaliendo(true);
    await salir();
    setSaliendo(false);
    navigate("/");
  };

  return (
    <div className="space-y-5">
      <section className="rounded-xl border border-border bg-card p-4">
        <div className="flex items-center gap-3">
          <span className="grid h-11 w-11 place-items-center rounded-full bg-primary text-primary-foreground">
            <UserRound className="h-5 w-5" />
          </span>
          <div className="min-w-0">
            {editando ? (
              <form onSubmit={guardar} className="flex gap-2">
                <input value={nuevoNombre} onChange={(e) => setNuevoNombre(e.target.value)} maxLength={80} aria-label="Nombre para mostrar" className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm" />
                <Button type="submit" size="sm">
                  Guardar
                </Button>
                <Button type="button" size="sm" variant="ghost" onClick={() => setEditando(false)}>
                  Cancelar
                </Button>
              </form>
            ) : (
              <h2 className="flex items-center gap-2 truncate text-base font-semibold">
                {nombre ?? "Sin nombre"}
                <button
                  type="button"
                  onClick={() => {
                    setNuevoNombre(perfil?.nombre ?? nombre ?? "");
                    setEditando(true);
                  }}
                  className="text-muted-foreground hover:text-foreground"
                  aria-label="Cambiar el nombre"
                >
                  <Pencil className="h-3.5 w-3.5" />
                </button>
              </h2>
            )}
            <p className="truncate text-sm text-muted-foreground">{usuario?.email}</p>
          </div>
        </div>
        <p className="mt-3 text-sm">
          Reputación: <span className="font-semibold">{perfil?.reputacion ?? 0}</span>
          <span className="text-muted-foreground"> · suma de los votos que recibieron tus reportes (a favor menos en contra).</span>
        </p>
        <p className="mt-1 text-xs text-muted-foreground">{POR_QUE_CUENTA}</p>
      </section>

      <section>
        <h2 className="text-sm font-semibold">Mi zona</h2>
        <p className="mb-2 text-xs text-muted-foreground">La ciudad con la que arrancan el mapa, las alertas y el chat cuando no usas el GPS. Se guarda en tu cuenta.</p>
        <CitySelector value={city} onChange={elegirZona} />
      </section>
      <Mensaje tipo={aviso?.tipo}>{aviso?.texto}</Mensaje>

      <section>
        <h2 className="text-sm font-semibold">Mis reportes</h2>
        {reportes.lista == null && !reportes.error && <Cargando />}
        {reportes.error && <ErrorCarga texto={reportes.error} onReintentar={cargarReportes} />}
        {reportes.lista?.length === 0 && <p className="mt-1 text-sm text-muted-foreground">Todavía no has hecho reportes.</p>}
        <ul className="mt-2 space-y-2">
          {reportes.lista?.map((r) => {
            const vive = vigente(r);
            return (
              <li key={r.id} className="rounded-lg border border-border bg-card px-3 py-2 text-sm">
                <div className="flex flex-wrap items-baseline gap-x-2">
                  <span className="font-semibold">{nombreReporte(r)}</span>
                  <span className="text-xs text-muted-foreground">{hace(r.creado_en)}</span>
                  <span className={cn("text-xs", vive ? "text-green-800" : "text-muted-foreground")}>{vive ? "vigente" : "vencido"}</span>
                </div>
                {r.descripcion && <p className="line-clamp-2 text-muted-foreground">{r.descripcion}</p>}
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {ESTADO_REPORTE[r.estado]} · {r.likes} a favor · {r.dislikes} en contra
                  {vive && (
                    <>
                      {" · "}
                      <Link to={`/comunidad/${r.id}`} className="underline">
                        Ver
                      </Link>
                    </>
                  )}
                </p>
              </li>
            );
          })}
        </ul>
      </section>

      <Button variant="outline" onClick={cerrar} disabled={saliendo}>
        <LogOut className="h-4 w-4" />
        {saliendo ? "Cerrando…" : "Cerrar sesión"}
      </Button>
    </div>
  );
}
