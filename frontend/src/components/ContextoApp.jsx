import { createContext, useContext } from "react";

// Lo que las páginas (Alertas, Comunidad, Chat, Cuenta, Histórico) necesitan del estado que vive
// en App: la zona de la persona, su posición, el panorama de alertas, los ríos vigilados y las
// acciones que mueven el mapa (que sigue vivo detrás de la página).
//   depto, porGps, userPos ([lat, lon] o null), city, ciudad, pickCity(nombre), geolocate()
//   p (usePanorama), rios (useRiosVigilados), pron
//   irAlMapa({ lat, lon, zoom })   centra el mapa ahí y vuelve a /
//   verRioEnMapa(rio)              prende el río y su zona, lo encuadra y vuelve a /
export const ContextoApp = createContext(null);

export function useApp() {
  const v = useContext(ContextoApp);
  if (!v) throw new Error("useApp necesita ContextoApp.Provider (App)");
  return v;
}
