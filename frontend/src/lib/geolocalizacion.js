// Ubicación del dispositivo con navigator.geolocation, en dos tiempos (módulo puro: lo prueban los
// tests con un navigator simulado; hooks/useGeolocation.js lo enchufa a React).
//
// Por qué dos tiempos: un solo getCurrentPosition con enableHighAccuracy y 8 s de espera falla
// en una computadora (no hay GPS: la ubicación sale de la red y el pedido de alta precisión se
// queda sin respuesta) y en el celular bajo techo (el GPS frío tarda más de 8 s). Google Maps
// ubica porque combina red y GPS y espera. Aquí:
//   1 lectura rápida de baja precisión (red o wifi, hasta 6 s; vale una de hace un minuto) para
//     tener algo ya, aunque sea a cientos de metros;
//   2 watchPosition de alta precisión hasta 22 s, quedándose con la mejor lectura (menor
//     `accuracy`) y parando antes si baja de 30 m.
// La precisión (metros) acompaña siempre a la posición: la persona ve "Precisión: unos 25 m".

export const LIMITES = {
  precisionBuenaM: 30, // con esta precisión o mejor se deja de afinar
  rapidaTimeoutMs: 6000, // lectura rápida (red): hasta 6 s
  rapidaMaximumAgeMs: 60_000, // vale una lectura de hace un minuto
  finaEsperaMs: 22_000, // afinado por GPS: hasta 22 s
};

export const opcionesRapida = (l = LIMITES) => ({ enableHighAccuracy: false, timeout: l.rapidaTimeoutMs, maximumAge: l.rapidaMaximumAgeMs });
export const opcionesFina = (l = LIMITES) => ({ enableHighAccuracy: true, timeout: l.finaEsperaMs, maximumAge: 0 });

// Códigos de GeolocationPositionError (los mismos en todos los navegadores).
const PERMISSION_DENIED = 1;
const TIMEOUT = 3;

// Una GeolocationPosition del navegador como { lat, lon, precisionM, hora }; precisionM null si el
// navegador no la informa.
export function lecturaDe(p) {
  const c = p?.coords ?? {};
  const precisionM = Number.isFinite(c.accuracy) && c.accuracy >= 0 ? Math.round(c.accuracy) : null;
  return { lat: c.latitude, lon: c.longitude, precisionM, hora: Number.isFinite(p?.timestamp) ? p.timestamp : null };
}

const valida = (l) => Boolean(l) && Number.isFinite(l.lat) && Number.isFinite(l.lon);

// La mejor de dos lecturas: la de menor precisionM; una precisión conocida le gana a una
// desconocida; en empate, la más nueva. Devuelve una de las dos (misma referencia), así quien
// compara sabe si cambió.
export function mejorLectura(a, b) {
  if (!valida(a)) return valida(b) ? b : null;
  if (!valida(b)) return a;
  const pa = a.precisionM;
  const pb = b.precisionM;
  if (pa == null && pb != null) return b;
  if (pb == null && pa != null) return a;
  if (pa != null && pb != null && pa !== pb) return pb < pa ? b : a;
  return (b.hora ?? 0) >= (a.hora ?? 0) ? b : a;
}

export const esPrecisa = (l, limite = LIMITES.precisionBuenaM) => valida(l) && l.precisionM != null && l.precisionM <= limite;

// Código propio a partir del error del navegador: denied | timeout | unavailable | insecure
// (Chrome en http sin localhost responde PERMISSION_DENIED con "Only secure origins are allowed").
export function codigoError(err) {
  const mensaje = String(err?.message ?? "").toLowerCase();
  if (mensaje.includes("secure origin") || mensaje.includes("secure context")) return "insecure";
  if (err?.code === PERMISSION_DENIED) return "denied";
  if (err?.code === TIMEOUT) return "timeout";
  return "unavailable";
}

// De dos fallos, el que más dice: "denied" > "insecure" > "unavailable" > "timeout".
const PESO = { denied: 4, insecure: 3, unavailable: 2, timeout: 1 };
export function peorCodigo(a, b) {
  if (!a) return b ?? null;
  if (!b) return a;
  return (PESO[b] ?? 0) > (PESO[a] ?? 0) ? b : a;
}

// El navegador solo entrega la ubicación en un contexto seguro (https o localhost).
export function contextoSeguro(win) {
  if (!win) return false;
  if (typeof win.isSecureContext === "boolean") return win.isSecureContext;
  const protocol = win.location?.protocol ?? "";
  const host = win.location?.hostname ?? "";
  return protocol === "https:" || host === "localhost" || host === "127.0.0.1" || host === "[::1]" || host.endsWith(".localhost");
}

// Lo que impide pedir la ubicación antes de intentarlo: "unavailable" (navegador sin
// geolocalización), "insecure" (http sin localhost) o null si se puede pedir.
export function revisarEntorno(win) {
  if (!win?.navigator?.geolocation) return "unavailable";
  if (!contextoSeguro(win)) return "insecure";
  return null;
}

// Estado del permiso con la Permissions API, si existe: "granted" | "denied" | "prompt" | null
// (null = no se sabe; se pide igual). Con "granted" la rápida y el GPS arrancan juntos; con
// "prompt" el GPS espera a la rápida, así el navegador muestra un solo pedido de permiso.
export async function estadoPermiso(nav) {
  try {
    const r = await nav?.permissions?.query?.({ name: "geolocation" });
    const s = r?.state;
    return s === "granted" || s === "denied" || s === "prompt" ? s : null;
  } catch {
    return null;
  }
}

// Pide la ubicación en dos tiempos. Devuelve { primera, cancelar }:
//   primera   Promise<Lectura> con la primera lectura (la rápida o la del GPS, la que llegue
//             antes); rechaza con { code: "denied" | "insecure" | "unavailable" | "timeout" |
//             "cancelado" } si no llegó ninguna
//   cancelar  () corta todo (al desmontar o al pedir de nuevo)
// opciones:
//   permiso   "granted" | "prompt" | "denied" | null (estadoPermiso)
//   rapida    false para solo afinar con el GPS (botón "Mejorar precisión")
//   desde     la mejor lectura que ya se tenía; solo se avisa si una nueva la mejora
//   onMejora  (lectura) cada vez que la mejor lectura cambia después de la primera
//   onFin     ({ motivo: "precisa" | "tiempo" | "error" | "cancelado", lectura, code }) al parar
//   limites, programar, desprogramar   LIMITES y setTimeout/clearTimeout (las pruebas los simulan)
export function ubicar(geolocation, opciones = {}) {
  const { permiso = null, rapida = true, desde = null, onMejora, onFin, limites = LIMITES, programar = setTimeout, desprogramar = clearTimeout } = opciones;
  let mejor = valida(desde) ? desde : null;
  let primeraResuelta = false;
  let terminado = false;
  let watchId = null;
  let temporizador = null;
  let errorRapida = null; // código del fallo de la lectura rápida, si falló
  let errorFina = null; // código del último fallo del GPS
  let rapidaPendiente = false;
  let finaArrancada = false;
  let resolver;
  let rechazar;
  const primera = new Promise((res, rej) => {
    resolver = res;
    rechazar = rej;
  });
  primera.catch(() => {}); // quien llama decide si le importa el rechazo

  const terminar = (motivo, code = null) => {
    if (terminado) return;
    terminado = true;
    if (watchId != null && typeof geolocation?.clearWatch === "function") geolocation.clearWatch(watchId);
    if (temporizador != null) desprogramar(temporizador);
    if (!primeraResuelta) {
      primeraResuelta = true;
      if (motivo === "error") rechazar({ code: code ?? "unavailable" });
      else if (motivo === "cancelado") rechazar({ code: "cancelado" });
      else if (mejor) resolver(mejor);
      else rechazar({ code: peorCodigo(errorRapida, errorFina) ?? "timeout" });
    }
    onFin?.({ motivo, lectura: mejor, code });
  };

  const recibir = (p) => {
    if (terminado) return;
    const l = lecturaDe(p);
    if (!valida(l)) return;
    const nueva = mejorLectura(mejor, l);
    const cambio = nueva !== mejor;
    mejor = nueva;
    if (!primeraResuelta) {
      primeraResuelta = true;
      resolver(mejor);
    } else if (cambio) onMejora?.(mejor);
    if (esPrecisa(mejor, limites.precisionBuenaM)) terminar("precisa");
  };

  const arrancarFina = () => {
    if (terminado || finaArrancada) return;
    finaArrancada = true;
    const fallo = (e) => {
      if (terminado) return;
      const code = codigoError(e);
      if (code === "denied" || code === "insecure") return terminar("error", code);
      errorFina = code;
      // sin ninguna lectura y con la rápida ya resuelta, no hay a quién esperar
      if (!mejor && !rapidaPendiente) terminar("error", peorCodigo(errorRapida, errorFina));
    };
    if (typeof geolocation.watchPosition === "function") watchId = geolocation.watchPosition(recibir, fallo, opcionesFina(limites));
    else geolocation.getCurrentPosition(recibir, fallo, opcionesFina(limites));
    temporizador = programar(() => terminar(mejor ? "tiempo" : "error", mejor ? null : peorCodigo(errorRapida, errorFina) ?? "timeout"), limites.finaEsperaMs);
  };

  const arrancarRapida = () => {
    rapidaPendiente = true;
    geolocation.getCurrentPosition(
      (p) => {
        rapidaPendiente = false;
        recibir(p);
        arrancarFina();
      },
      (e) => {
        rapidaPendiente = false;
        if (terminado) return;
        const code = codigoError(e);
        if (code === "denied" || code === "insecure") return terminar("error", code);
        errorRapida = code;
        if (!finaArrancada) arrancarFina();
        else if (errorFina && !mejor) terminar("error", peorCodigo(errorRapida, errorFina));
      },
      opcionesRapida(limites)
    );
  };

  if (permiso === "denied") terminar("error", "denied");
  else if (!rapida) arrancarFina();
  else {
    arrancarRapida();
    if (permiso === "granted") arrancarFina();
  }

  return { primera, cancelar: () => terminar("cancelado") };
}

// Textos por estado del hook (status): la persona siempre sabe qué pasó y qué puede hacer.
export const TEXTO_ESTADO = {
  idle: "Se necesita tu ubicación.",
  pending: "Buscando tu ubicación… puede tardar hasta medio minuto si el GPS estaba apagado.",
  denied:
    "No diste permiso de ubicación. Para activarlo toca el candado o el ícono de ubicación junto a la dirección de la página, permite la ubicación y vuelve a intentar. En el celular revisa además que la ubicación del sistema esté prendida.",
  unavailable:
    "No se pudo determinar tu ubicación. En el celular, prende la ubicación y sal a cielo abierto. En una computadora la ubicación es aproximada (sale de la red, no de un GPS) y a veces el sistema la tiene apagada.",
  timeout: "Tu GPS tarda demasiado en responder. Sal a cielo abierto o acércate a una ventana y vuelve a intentar.",
  insecure: "El navegador solo entrega la ubicación en páginas seguras (https). Abre la dirección con https:// y vuelve a intentar.",
};

// Mientras se busca, desde el primer intento: bajo techo el GPS frío puede ocupar los 6 s de la
// lectura rápida más los 22 s del afinado, y la persona no debe ver un botón girando medio minuto
// sin explicación. Al reintentar (`deNuevo`) se dice que se busca de nuevo.
export function textoBuscando(deNuevo = false) {
  return deNuevo ? "Buscando tu ubicación de nuevo… puede tardar hasta medio minuto." : TEXTO_ESTADO.pending;
}

// Un fallo, en corto, para la hoja de bienvenida del mapa (OnboardingGps), donde la salida es
// elegir la ciudad; `ciudad` es el nombre de la ciudad que se muestra mientras tanto.
export function textoFalloCorto(status, ciudad = "Cajamarca") {
  switch (status) {
    case "denied":
      return "No diste permiso de ubicación (se activa en el candado o el ícono de ubicación junto a la dirección). Mientras tanto, elige tu ciudad.";
    case "insecure":
      return "La ubicación solo funciona en páginas seguras (https). Elige tu ciudad.";
    case "timeout":
      return `Tu GPS tarda: sal a cielo abierto y vuelve a intentar. Mientras tanto te mostramos ${ciudad}; elige tu ciudad si es otra.`;
    default:
      return `No se pudo determinar tu ubicación (en una computadora suele ser aproximada o estar apagada). Mientras tanto te mostramos ${ciudad}; elige tu ciudad si es otra.`;
  }
}

// Vale la pena volver a intentar con este estado (en denied e insecure primero hay que cambiar algo).
export const sePuedeReintentar = (status) => status === "timeout" || status === "unavailable";

// Estados del hook con los que no hubo ubicación por un fallo (y se avisa qué pasó).
export const esFalloGps = (status) => status === "denied" || status === "unavailable" || status === "timeout" || status === "insecure";

// Sin ubicación en "Tu zona ahora" (TuZona), donde las distancias se miden desde el centro de la
// ciudad: qué pasó según el estado y el enlace que corresponde ("Usar mi ubicación" si todavía no
// se pidió, "Volver a intentar" cuando reintentar tiene sentido, ninguno si antes hay que cambiar
// algo: permiso negado o página sin https). -> { texto, enlace }
export function textoSinGps(status) {
  const enlace = sePuedeReintentar(status) ? "Volver a intentar" : null;
  switch (status) {
    case "denied":
      return { texto: "No pudimos usar tu ubicación: las distancias van desde el centro de la ciudad.", enlace };
    case "insecure":
      return { texto: `${TEXTO_ESTADO.insecure} Mientras tanto, las distancias van desde el centro de la ciudad.`, enlace };
    case "timeout":
      return { texto: "Tu GPS tardó en responder: sal a cielo abierto y vuelve a intentar.", enlace };
    case "unavailable":
      return { texto: "No pudimos usar tu ubicación: las distancias van desde el centro de la ciudad. En el celular, prende la ubicación y sal a cielo abierto.", enlace };
    default:
      return { texto: "Activa tu ubicación para ver a qué distancia estás tú del río.", enlace: "Usar mi ubicación" };
  }
}

// Cuán buena es la precisión: buena (≤ 30 m), regular (≤ 150 m), baja (más) o null si no se sabe.
export function calidadPrecision(m, limite = LIMITES.precisionBuenaM) {
  if (m == null || !Number.isFinite(m)) return null;
  if (m <= limite) return "buena";
  if (m <= 150) return "regular";
  return "baja";
}

// Metros redondeados para leer: 9 m, 25 m, 180 m, 1,5 km, 12 km.
export function textoMetrosPrecision(m) {
  if (m == null || !Number.isFinite(m) || m < 0) return null;
  if (m < 10) return `${Math.max(1, Math.round(m))} m`;
  if (m < 100) return `${Math.round(m / 5) * 5} m`;
  if (m < 1000) return `${Math.round(m / 10) * 10} m`;
  const km = m / 1000;
  const texto = km < 10 ? (Math.round(km * 10) / 10).toFixed(1).replace(".", ",") : String(Math.round(km));
  return `${texto} km`;
}

// "Precisión: unos 25 m (buena)"; sin precisión informada, "Precisión desconocida".
export function textoPrecision(m) {
  const metros = textoMetrosPrecision(m);
  if (!metros) return "Precisión desconocida";
  return `Precisión: unos ${metros} (${calidadPrecision(m)})`;
}

// Aviso cuando el punto puede quedar lejos de donde está la persona (precisión baja o desconocida).
export function avisoPrecision(m) {
  const calidad = calidadPrecision(m);
  if (calidad === "buena" || calidad === "regular") return null;
  return calidad == null
    ? "El navegador no informó la precisión: el punto puede quedar lejos de donde estás. Prueba Mejorar precisión."
    : "Con esta precisión el reporte podría marcarse lejos de donde estás. Prueba Mejorar precisión o sal a cielo abierto.";
}
