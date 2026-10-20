import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, RefreshCw } from "lucide-react";
import PanelPagina from "@/components/PanelPagina";
import TarjetaReporte from "@/components/TarjetaReporte";
import { Cargando, EntraPara, ErrorCarga, Vacio } from "@/components/EstadoCarga";
import { Button } from "@/components/ui/button";
import { useApp } from "@/components/ContextoApp";
import { useSesion } from "@/hooks/useSesion";
import { getMisVotos, getReportesComunidad } from "@/lib/queries";
import { ordenarReportes } from "@/lib/comunidad";

const CADA_MS = 2 * 60_000;

// Reportes ciudadanos vigentes (la BD solo entrega los de las últimas 12 h), ordenados por
// confianza y cercanía a la persona (su GPS o la ciudad elegida).
export default function Comunidad() {
  const { userPos, ciudad, porGps, irAlMapa } = useApp();
  const { conSesion, cargando: cargandoSesion } = useSesion();
  const [estado, setEstado] = useState({ reportes: null, error: false });
  const [misVotos, setMisVotos] = useState({});
  const pos = useMemo(() => (userPos ? { lat: userPos[0], lon: userPos[1] } : { lat: ciudad.lat, lon: ciudad.lon }), [userPos, ciudad]);

  const cargar = useCallback(
    async (fresco = false) => {
      try {
        const reportes = await getReportesComunidad({ fresco });
        setEstado({ reportes, error: false });
        if (conSesion) setMisVotos(await getMisVotos(reportes.map((r) => r.id)).catch(() => ({})));
      } catch (e) {
        console.error("comunidad", e);
        setEstado((s) => ({ reportes: s.reportes, error: true }));
      }
    },
    [conSesion]
  );
  useEffect(() => {
    cargar();
    const id = setInterval(() => cargar(true), CADA_MS);
    return () => clearInterval(id);
  }, [cargar]);

  const lista = useMemo(() => ordenarReportes(estado.reportes ?? [], pos), [estado.reportes, pos]);
  const alCambiar = (nuevo, voto) => {
    setEstado((s) => ({ ...s, reportes: s.reportes?.map((r) => (r.id === nuevo.id ? { ...r, ...nuevo } : r)) ?? null }));
    setMisVotos((v) => ({ ...v, [nuevo.id]: voto }));
  };

  return (
    <PanelPagina
      titulo="Comunidad"
      subtitulo="Reportes de vecinos, validados por la misma comunidad con sus votos. Duran 12 horas."
      disclaimer
      acciones={
        <Button variant="ghost" size="icon" className="h-9 w-9" onClick={() => cargar(true)} aria-label="Actualizar la lista">
          <RefreshCw className="h-4 w-4" />
        </Button>
      }
    >
      <Button asChild variant="destructive" className="mb-3 w-full">
        <Link to="/comunidad/nuevo">
          <Plus className="h-[18px] w-[18px]" />
          Reportar incidente
        </Link>
      </Button>
      {!cargandoSesion && !conSesion && <EntraPara que="reportar, votar y comentar" compacto className="mb-3" />}
      <p className="mb-3 text-xs text-muted-foreground">
        {porGps && userPos ? "Distancias desde tu ubicación." : `Distancias desde ${ciudad.name} (la ciudad elegida).`} Primero los reportes con más apoyo de la comunidad y más cercanos.
      </p>
      {estado.reportes == null && !estado.error && <Cargando texto="Cargando los reportes…" />}
      {estado.error && <ErrorCarga texto="No se pudieron cargar los reportes." onReintentar={() => cargar(true)} />}
      {estado.reportes != null && lista.length === 0 && (
        <Vacio titulo="No hay reportes vigentes ahora." texto="Cada reporte dura 12 horas. Si ves algo en tu zona, repórtalo desde donde estás." />
      )}
      <div className="space-y-2">
        {lista.map((r) => (
          <TarjetaReporte key={r.id} r={r} miVoto={misVotos[r.id] ?? null} onCambio={alCambiar} onVerMapa={(x) => irAlMapa({ lat: x.lat, lon: x.lon, zoom: 16 })} />
        ))}
      </div>
    </PanelPagina>
  );
}
