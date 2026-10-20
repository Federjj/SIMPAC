import { useRef, useState } from "react";
import { LocateFixed, MapPin } from "lucide-react";
import { Button } from "@/components/ui/button";
import CitySelector from "@/components/CitySelector";
import { marcarGpsVisto } from "@/lib/zonaAhora";
import { useAltoHoja } from "@/hooks/useAltoHoja";

// Una pantalla antes de pedir el permiso del GPS: explica para qué sirve la ubicación y que no se
// guarda. Hoja a media altura sobre el mapa (no tapa la pantalla). Se muestra una vez (localStorage
// simpac.gps = "visto"; sin localStorage vuelve a salir, aceptable); el botón "Mi ubicación" de la
// derecha sigue siempre. Si el navegador ya tenía el permiso, App pide el GPS solo y esto no sale.
//   ciudad     la ciudad elegida (para decir qué se muestra mientras tanto)
//   city/pickCity   el selector de ciudad (CitySelector)
//   geolocate  () -> Promise<[lat, lon] | null>  (App)
//   status     idle | pending | granted | denied | unavailable (useGeolocation)
//   onCerrar   () -> la hoja se va (concedido, ciudad elegida o "Ahora no")
export default function OnboardingGps({ ciudad, city, pickCity, geolocate, status, onCerrar }) {
  const [paso, setPaso] = useState("inicio"); // inicio | ciudad | fallo
  const pidiendo = status === "pending";
  const hojaRef = useRef(null);
  useAltoHoja(hojaRef);
  // el mensaje del fallo se arma al dibujar, con el status ya actualizado (denegado o sin GPS)
  const mensaje =
    paso === "fallo"
      ? status === "denied" || typeof navigator === "undefined" || !navigator.geolocation
        ? "No pudimos usar tu ubicación. Elige tu ciudad."
        : `Tu GPS tarda o no responde; mientras tanto te mostramos ${ciudad?.name ?? "Cajamarca"}. Elige tu ciudad si es otra.`
      : null;

  const usar = async () => {
    marcarGpsVisto();
    const lugar = await geolocate();
    if (lugar) {
      onCerrar();
      return;
    }
    setPaso("fallo"); // denegado o sin GPS: se dice y se ofrece la ciudad
  };
  const elegirCiudad = () => {
    marcarGpsVisto();
    setPaso("ciudad");
  };
  const ahoraNo = () => {
    marcarGpsVisto();
    onCerrar();
  };

  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-0 z-[700] p-3 md:p-4 lg:left-4 lg:right-auto lg:w-[420px] lg:max-w-[calc(100%-2rem)]">
      <section
        ref={hojaRef}
        role="dialog"
        aria-labelledby="gps-titulo"
        data-tapa-mapa="abajo"
        className="hoja hoja-entra pointer-events-auto rounded-2xl border border-border bg-card/95 p-4 shadow-2xl backdrop-blur"
      >
        <div className="flex items-start gap-3">
          <div className="gps-disco grid h-12 w-12 shrink-0 place-items-center rounded-full bg-primary text-primary-foreground" aria-hidden="true">
            <LocateFixed className="h-6 w-6" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 id="gps-titulo" className="text-lg font-semibold leading-tight">
              Mira cómo está tu zona
            </h2>
            <p className="mt-1 text-sm leading-snug text-muted-foreground">
              Con tu ubicación te decimos a qué distancia estás del río vigilado y de la zona que podría inundarse, y qué puntos de
              ayuda tienes cerca. Tu ubicación se queda en tu teléfono: no la guardamos ni la mostramos a nadie.
            </p>
          </div>
        </div>

        {mensaje && (
          <p role="status" className="mt-3 rounded-lg bg-nivel-alerta/10 px-3 py-2 text-sm font-medium text-nivel-alerta">
            {mensaje}
          </p>
        )}

        {paso === "ciudad" || paso === "fallo" ? (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <CitySelector
              value={city}
              onChange={(nombre) => {
                pickCity(nombre);
                onCerrar();
              }}
            />
            <Button variant="ghost" size="sm" onClick={onCerrar}>
              Seguir con {ciudad?.name ?? "la ciudad elegida"}
            </Button>
          </div>
        ) : (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button className="h-10 flex-1 font-semibold" onClick={usar} disabled={pidiendo}>
              <LocateFixed className="h-4 w-4" />
              {pidiendo ? "Buscando tu ubicación…" : "Usar mi ubicación"}
            </Button>
            <Button variant="outline" className="h-10" onClick={elegirCiudad} disabled={pidiendo}>
              <MapPin className="h-4 w-4" />
              Elegir mi ciudad
            </Button>
            <button type="button" onClick={ahoraNo} className="w-full py-1 text-center text-sm text-muted-foreground underline underline-offset-2 hover:text-foreground sm:w-auto sm:px-2">
              Ahora no
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
