import { useCallback, useState } from "react";

// Qué capas están encendidas (arranca con el defaultVisible de cada una) y la opción
// elegida en las que tienen selector (p. ej. el evento FEN, "ayer" o "7 días"). Las capas con
// el mismo opciones.vinculo comparten la opción: elegir el día de los avisos cambia también el
// del pronóstico.
export function useLayerVisibility(layers) {
  const [visible, setVisible] = useState(() =>
    Object.fromEntries(layers.map((l) => [l.id, Boolean(l.defaultVisible)]))
  );
  const [opciones, setOpciones] = useState(() =>
    Object.fromEntries(layers.filter((l) => l.opciones).map((l) => [l.id, l.opciones.defecto]))
  );
  const toggle = useCallback((id) => setVisible((v) => ({ ...v, [id]: !v[id] })), []);
  const mostrar = useCallback((id, on = true) => setVisible((v) => ({ ...v, [id]: on })), []);
  const elegir = useCallback(
    (id, valor) =>
      setOpciones((o) => {
        const vinculo = layers.find((l) => l.id === id)?.opciones?.vinculo;
        const ids = vinculo ? layers.filter((l) => l.opciones?.vinculo === vinculo).map((l) => l.id) : [id];
        return { ...o, ...Object.fromEntries(ids.map((x) => [x, valor])) };
      }),
    [layers]
  );
  return { visible, toggle, mostrar, opciones, elegir };
}
