import { createContext, createElement, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { supabase } from "@/lib/supabaseClient";
import { leerPerfil } from "@/lib/sesion";

// Sesión de Supabase Auth para toda la app (onAuthStateChange) y el perfil propio.
//   usuario      el user de Supabase o null
//   perfil       { id, nombre, reputacion, ciudad } o null (se lee al entrar; recargarPerfil() lo pide de nuevo)
//   cargando     true hasta que se sabe si hay sesión (INITIAL_SESSION): las páginas no dicen
//                "entra para..." antes de tiempo
//   recuperacion true si la persona llegó desde el correo de "olvidé mi contraseña"
//                (PASSWORD_RECOVERY): Cuenta muestra el formulario de contraseña nueva
//   nombre       cómo llamarla: el nombre del perfil, el del registro o la parte local del correo
const Contexto = createContext(null);

export function SesionProvider({ children }) {
  const [usuario, setUsuario] = useState(null);
  const [perfil, setPerfil] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [recuperacion, setRecuperacion] = useState(false);

  const recargarPerfil = useCallback(async () => {
    const r = await leerPerfil();
    if (r.ok) setPerfil(r.perfil);
    return r;
  }, []);

  useEffect(() => {
    const { data } = supabase.auth.onAuthStateChange((evento, sesion) => {
      setUsuario(sesion?.user ?? null);
      if (evento === "INITIAL_SESSION") setCargando(false);
      if (evento === "PASSWORD_RECOVERY") setRecuperacion(true);
      if (evento === "SIGNED_OUT") {
        setPerfil(null);
        setRecuperacion(false);
      }
      // el perfil se lee fuera del callback (supabase-js pide no esperar otra llamada dentro)
      if (sesion?.user && (evento === "SIGNED_IN" || evento === "INITIAL_SESSION" || evento === "USER_UPDATED")) {
        setTimeout(() => {
          leerPerfil().then((r) => r.ok && setPerfil(r.perfil));
        }, 0);
      }
    });
    return () => data.subscription.unsubscribe();
  }, []);

  const valor = useMemo(() => {
    const correo = usuario?.email ?? "";
    const nombre = perfil?.nombre || usuario?.user_metadata?.nombre || (correo ? correo.split("@")[0] : null);
    return {
      usuario,
      perfil,
      cargando,
      recuperacion,
      nombre,
      conSesion: Boolean(usuario),
      recargarPerfil,
      terminarRecuperacion: () => setRecuperacion(false),
    };
  }, [usuario, perfil, cargando, recuperacion, recargarPerfil]);

  return createElement(Contexto.Provider, { value: valor }, children);
}

export function useSesion() {
  const v = useContext(Contexto);
  if (!v) throw new Error("useSesion necesita SesionProvider");
  return v;
}
