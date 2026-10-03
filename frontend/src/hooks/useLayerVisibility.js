import { useCallback, useEffect, useRef, useState } from "react";
import { fechaPeru } from "@/lib/tiempo";
import { supabase } from "@/lib/supabaseClient";
import { CLAVE, aplicar, borrarLocal, guardarLocal, leerLocal, masReciente, serializar } from "@/lib/preferencias";

// Qué capas están encendidas (arranca con el defaultVisible de cada una) y la opción elegida en las
// que tienen selector (p. ej. el evento FEN, "ayer" o "7 días"), recordadas en este navegador
// (localStorage, lib/preferencias.js) y, si hay sesión de Supabase Auth, en la tabla
// preferencia_mapa (RLS: cada quien solo la suya). Las capas con el mismo opciones.vinculo comparten
// la opción: elegir el día de los avisos cambia también el del pronóstico (y ese día se recuerda
// solo durante esa fecha de Perú). Sin localStorage (ventana privada, datos bloqueados) el mapa
// arranca con los valores de siempre y no se rompe.
//
// Devuelve, además de { visible, toggle, mostrar, opciones, elegir }:
//   nuevas        ids de capas que no existían la última vez (el panel les pone "Nueva")
//   conocerTodas  () -> las marca como vistas (App: al cerrar el panel de capas)
//   cambios       true si algo difiere de lo de siempre (el panel muestra "Restablecer capas")
//   restablecer   () -> vuelve a los defectos y borra lo guardado
//   dondeGuarda   "cuenta" | "navegador" | null (este navegador no deja guardar)
const ESPERA_BD_MS = 1500;

export function useLayerVisibility(layers) {
  const [inicio] = useState(() => {
    const crudo = leerLocal();
    return { ...aplicar(layers, crudo, { hoy: fechaPeru() }), guardado: crudo?.guardado ?? null };
  });
  const [visible, setVisible] = useState(inicio.visible);
  const [opciones, setOpciones] = useState(inicio.opciones);
  const [nuevas, setNuevas] = useState(inicio.nuevas);
  const [cambios, setCambios] = useState(inicio.cambios);
  const [usuario, setUsuario] = useState(null);
  const [sinGuardar, setSinGuardar] = useState(false);
  // conocidas: las que la persona ya vio (las nuevas se suman al cerrar el panel)
  const conocidas = useRef(layers.map((l) => l.id).filter((id) => !inicio.nuevas.includes(id)));
  // cuándo cambió algo la persona (null = nunca): un celular nuevo no pisa la cuenta
  const guardado = useRef(inicio.guardado);
  const porLaPersona = useRef(false);

  const marcar = () => {
    porLaPersona.current = true;
    guardado.current = new Date().toISOString();
  };
  const toggle = useCallback((id) => {
    marcar();
    setVisible((v) => ({ ...v, [id]: !v[id] }));
  }, []);
  const mostrar = useCallback((id, on = true) => {
    marcar();
    setVisible((v) => ({ ...v, [id]: on }));
  }, []);
  const elegir = useCallback(
    (id, valor) => {
      marcar();
      setOpciones((o) => {
        const vinculo = layers.find((l) => l.id === id)?.opciones?.vinculo;
        const ids = vinculo ? layers.filter((l) => l.opciones?.vinculo === vinculo).map((l) => l.id) : [id];
        return { ...o, ...Object.fromEntries(ids.map((x) => [x, valor])) };
      });
    },
    [layers]
  );

  // guardar: en el navegador al instante; en la cuenta, 1,5 s después del último cambio
  useEffect(() => {
    const datos = serializar(layers, { visible, opciones }, { hoy: fechaPeru(), conocidas: conocidas.current, guardado: guardado.current });
    setSinGuardar(!guardarLocal(datos));
    setCambios(Object.keys(datos.capas).length > 0 || Object.keys(datos.opciones).length > 0 || Boolean(datos.dia));
    if (!usuario || !porLaPersona.current) return undefined;
    const t = setTimeout(() => {
      supabase
        .from("preferencia_mapa")
        .upsert({ usuario, version: datos.v, datos }, { onConflict: "usuario" })
        .then(({ error }) => error && console.warn("preferencias: no se guardaron en la cuenta", error.message));
    }, ESPERA_BD_MS);
    return () => clearTimeout(t);
  }, [layers, visible, opciones, usuario, nuevas]); // nuevas: al cerrar el panel se guardan las conocidas

  // sesión: al entrar se usa la copia más reciente (la del navegador o la de la cuenta)
  useEffect(() => {
    let vivo = true;
    const { data } = supabase.auth.onAuthStateChange((evento, sesion) => {
      const id = sesion?.user?.id ?? null;
      setUsuario(id);
      if (!id || (evento !== "SIGNED_IN" && evento !== "INITIAL_SESSION")) return;
      // fuera del callback: supabase-js recomienda no esperar otra llamada dentro de él
      setTimeout(async () => {
        const { data: fila, error } = await supabase.from("preferencia_mapa").select("datos").maybeSingle();
        if (!vivo || error) return;
        const local = leerLocal();
        const elegido = masReciente(local, fila?.datos ?? null);
        if (!elegido || elegido === local) return; // lo del navegador es igual o más nuevo: se sube en el próximo cambio
        const r = aplicar(layers, elegido, { hoy: fechaPeru() });
        guardado.current = elegido.guardado ?? null;
        porLaPersona.current = false;
        setVisible(r.visible);
        setOpciones(r.opciones);
      }, 0);
    });
    return () => {
      vivo = false;
      data.subscription.unsubscribe();
    };
  }, [layers]);

  // otra pestaña cambió las capas: seguirla (evento "storage" del navegador; key null = se borró todo)
  useEffect(() => {
    const alCambiar = (e) => {
      if (e.key !== CLAVE && e.key !== null) return;
      const crudo = leerLocal();
      const r = aplicar(layers, crudo, { hoy: fechaPeru() });
      guardado.current = crudo?.guardado ?? null;
      porLaPersona.current = false;
      // lo que la otra pestaña ya conoce cuenta como conocido aquí también: si no, cada pestaña
      // volvería a escribir su lista y se pisarían una a otra sin fin
      const vistas = new Set([...conocidas.current, ...(Array.isArray(crudo?.conocidas) ? crudo.conocidas : [])]);
      conocidas.current = layers.map((l) => l.id).filter((id) => vistas.has(id));
      setNuevas((n) => (n.some((id) => vistas.has(id)) ? n.filter((id) => !vistas.has(id)) : n));
      setVisible(r.visible);
      setOpciones(r.opciones);
    };
    window.addEventListener("storage", alCambiar);
    return () => window.removeEventListener("storage", alCambiar);
  }, [layers]);

  const conocerTodas = useCallback(() => {
    if (!nuevas.length) return;
    conocidas.current = layers.map((l) => l.id);
    setNuevas([]);
  }, [layers, nuevas]);

  const restablecer = useCallback(() => {
    const r = aplicar(layers, null, { hoy: fechaPeru() });
    borrarLocal();
    marcar(); // en la cuenta también vuelve a lo de siempre
    setVisible(r.visible);
    setOpciones(r.opciones);
  }, [layers]);

  return {
    visible, toggle, mostrar, opciones, elegir,
    nuevas, conocerTodas, cambios, restablecer,
    dondeGuarda: usuario ? "cuenta" : sinGuardar ? null : "navegador",
  };
}
