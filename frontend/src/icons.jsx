// Íconos SVG (NO emojis). Set consistente estilo "line".
const I = ({ size = 20, children }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">{children}</svg>
);

export const IcMapa = (p) => <I {...p}><path d="M9 20l-5.4 1.8V6L9 4m0 16l6 2m-6-2V4m6 18l5.4-1.8V4.2L15 6m0 16V6m0 0L9 4" /></I>;
export const IcAlerta = (p) => <I {...p}><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" /><path d="M12 9v4M12 17h.01" /></I>;
export const IcComunidad = (p) => <I {...p}><path d="M3 11l18-5v12L3 14z" /><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6" /></I>;
export const IcChat = (p) => <I {...p}><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></I>;
export const IcCuenta = (p) => <I {...p}><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></I>;
export const IcLogin = (p) => <I {...p}><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4M10 17l5-5-5-5M15 12H3" /></I>;
export const IcLayers = (p) => <I {...p}><path d="M12 2 2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" /></I>;
export const IcLocate = (p) => <I {...p}><circle cx="12" cy="12" r="3" /><path d="M12 2v3m0 14v3m10-10h-3M5 12H2" /></I>;
export const IcPlus = (p) => <I {...p}><path d="M12 5v14M5 12h14" /></I>;
export const IcRain = (p) => <I {...p}><path d="M20 16.6A5 5 0 0 0 18 7h-1.3A7 7 0 1 0 4 15M8 19v2m4-3v3m4-4v2" /></I>;
export const IcRiver = (p) => <I {...p}><path d="M3 12h4l3 8 4-16 3 8h4" /></I>;
export const IcTemp = (p) => <I {...p}><path d="M14 14.76V5a2 2 0 1 0-4 0v9.76a4 4 0 1 0 4 0z" /></I>;
export const IcStation = (p) => <I {...p}><path d="M12 22s8-4.5 8-11a8 8 0 1 0-16 0c0 6.5 8 11 8 11z" /><circle cx="12" cy="11" r="3" /></I>;
export const IcUsers = (p) => <I {...p}><path d="M17 21v-2a4 4 0 0 0-3-3.9M9 21v-2a4 4 0 0 1 3-3.9" /><circle cx="12" cy="8" r="3" /></I>;
export const IcZone = (p) => <I {...p}><circle cx="12" cy="12" r="9" /><path d="M12 8v4M12 16h.01" /></I>;
export const IcBell = (p) => <I {...p}><path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0" /></I>;
export const IcPin = (p) => <I {...p}><path d="M12 21s7-6 7-11a7 7 0 1 0-14 0c0 5 7 11 7 11z" /><circle cx="12" cy="10" r="2.5" /></I>;
export const IcChevron = (p) => <I {...p}><path d="M6 9l6 6 6-6" /></I>;
