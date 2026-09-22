import { useCallback, useState } from "react";

// Qué capas están encendidas: arranca con el defaultVisible de cada una.
export function useLayerVisibility(layers) {
  const [visible, setVisible] = useState(() =>
    Object.fromEntries(layers.map((l) => [l.id, Boolean(l.defaultVisible)]))
  );
  const toggle = useCallback((id) => setVisible((v) => ({ ...v, [id]: !v[id] })), []);
  return { visible, toggle };
}
