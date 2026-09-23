// Acomodo en pantalla de las insignias de los avisos y los discos del pronóstico (puro: sin
// Leaflet; lo usa map/acomodo.js con las posiciones en píxeles de la vista actual).
//
// items: [{id, x, y, w, h, prioridad, tipo:"usuario"|"insignia"|"disco", clave?, candidatos?:[{dx,dy}], rotulo?:{w,h}}]
// devuelve Map id -> {estado:"visible"|"punto"|"oculto"|"fusionado", dx, dy, en?, fusionados:[ids], rotulo:"der"|"izq"|null}
//
// Voraz, con cajas centradas en (x+dx, y+dy):
//   1. el disco del usuario (su localidad) siempre, con su rótulo: a la derecha, o a la izquierda
//      si de ese lado tapa menos insignias, paneles o marcadores de otras capas;
//   2. las insignias por prioridad: si tocan otra insignia ya puesta se juntan en ella ("2 avisos");
//      si tocan otra cosa prueban sus candidatos (lugares dentro de su zona) y si no, se ocultan
//      (salvo que solo tapen el rótulo del usuario: ahí se quedan, el rótulo va encima; o que
//      tapen su disco: ahí se pegan a su lado, porque a escala país la zona mide pocos píxeles,
//      ningún candidato cae dentro y el aviso de tu zona no debe desaparecer);
//   3. los discos por prioridad: si tocan algo (también un marcador de otra capa) pasan a ser un
//      punto de color (que no ocupa lugar);
//   4. los rótulos de los discos visibles: a la derecha, a la izquierda si no caben, o ninguno.
// `ancho` (opcional) es el ancho de la vista: un rótulo que se sale de ella no cabe.
// `obstaculos` (opcional): cajas {x, y, w, h} tapadas por la interfaz (chips, paneles); las
// insignias y los rótulos las evitan (un disco bajo un panel igual queda tapado: no se toca).
// `fijos` (opcional): cajas {x, y, w, h} de los marcadores de otras capas (ríos, estaciones...);
// un disco encima pasa a punto y los rótulos los evitan (las insignias de los avisos no se mueven).
const SEPARACION_ROTULO = 18; // del centro del disco al borde del rótulo (el CSS usa lo mismo)

const porPrioridad = (a, b) => b.prioridad - a.prioridad;

export function colocar(items, { margen = 2, ancho = Infinity, obstaculos = [], fijos = [] } = {}) {
  const res = new Map();
  const puestas = []; // cajas ocupadas: {x, y, w, h, id, tipo}
  const toca = (a, b) => Math.abs(a.x - b.x) < (a.w + b.w) / 2 + margen && Math.abs(a.y - b.y) < (a.h + b.h) / 2 + margen;
  const bajoUi = (c) => obstaculos.some((o) => toca(c, o));
  const sobreFijo = (c) => fijos.some((f) => toca(c, f));
  const libre = (c, { ui = true, fijo = true } = {}) =>
    !puestas.some((p) => toca(c, p)) && !(ui && bajoUi(c)) && !(fijo && sobreFijo(c));
  const caja = (it, dx = 0, dy = 0) => ({ x: it.x + dx, y: it.y + dy, w: it.w, h: it.h, id: it.id, tipo: it.tipo });
  const cabe = (c) => c.x - c.w / 2 >= 0 && c.x + c.w / 2 <= ancho;
  const cajaRotulo = (it, r, lado) => {
    const cx = it.x + r.dx + (lado === "der" ? 1 : -1) * (SEPARACION_ROTULO + it.rotulo.w / 2);
    return { x: cx, y: it.y + r.dy, w: it.rotulo.w, h: it.rotulo.h, id: `${it.id}:rotulo`, tipo: "rotulo" };
  };
  // lugares de la insignia `it` pegada al disco `u`: a la izquierda (el rótulo suele ir a la
  // derecha), abajo, arriba y a la derecha
  const pegados = (it, u) => {
    const sx = (it.w + u.w) / 2 + margen + 1;
    const sy = (it.h + u.h) / 2 + margen + 1;
    return [[-sx, 0], [0, sy], [0, -sy], [sx, 0]].map(([ox, oy]) => ({ dx: u.x + ox - it.x, dy: u.y + oy - it.y }));
  };
  for (const it of items) res.set(it.id, { estado: "oculto", dx: 0, dy: 0, fusionados: [], rotulo: null });

  // 1. el usuario: siempre, con su rótulo del lado que tape menos (insignias en su lugar, paneles,
  //    marcadores de otras capas)
  const insignias = items.filter((i) => i.tipo === "insignia").sort(porPrioridad);
  for (const it of items.filter((i) => i.tipo === "usuario")) {
    const r = res.get(it.id);
    r.estado = "visible";
    puestas.push(caja(it));
    if (!it.rotulo) continue;
    const tapa = (c) =>
      (bajoUi(c) ? 100 : 0) + insignias.filter((i) => toca(c, caja(i))).length + fijos.filter((f) => toca(c, f)).length;
    const [der, izq] = [cajaRotulo(it, r, "der"), cajaRotulo(it, r, "izq")];
    r.rotulo = !cabe(der) || (cabe(izq) && tapa(izq) < tapa(der)) ? "izq" : "der";
    puestas.push(r.rotulo === "der" ? der : izq);
  }

  // 2. las insignias (los marcadores de otras capas no las mueven)
  const libreInsignia = (c) => libre(c, { fijo: false });
  for (const it of insignias) {
    const r = res.get(it.id);
    const c = caja(it);
    const otra = puestas.find((p) => p.tipo === "insignia" && toca(c, p));
    if (otra) {
      r.estado = "fusionado";
      r.en = otra.id;
      res.get(otra.id).fusionados.push(it.id);
      continue;
    }
    let lugar = libreInsignia(c) ? { dx: 0, dy: 0 } : (it.candidatos ?? []).find((d) => libreInsignia(caja(it, d.dx, d.dy)));
    // si lo único que tapa es el rótulo del usuario, la insignia no se pierde
    if (!lugar && !bajoUi(c) && puestas.every((p) => p.tipo === "rotulo" || !toca(c, p))) lugar = { dx: 0, dy: 0 };
    // si tapa el disco del usuario y no le queda candidato, se pega a su lado (sin taparlo)
    const u = !lugar && puestas.find((p) => p.tipo === "usuario" && toca(c, p));
    if (u) lugar = pegados(it, u).find((d) => libreInsignia(caja(it, d.dx, d.dy)));
    if (!lugar) continue; // oculto
    r.estado = "visible";
    r.dx = lugar.dx;
    r.dy = lugar.dy;
    puestas.push(caja(it, lugar.dx, lugar.dy));
  }

  // 3. los discos (sobre un marcador de otra capa también pasan a punto: no lo tapan)
  const discos = items.filter((i) => i.tipo === "disco").sort(porPrioridad);
  for (const it of discos) {
    const r = res.get(it.id);
    const c = caja(it);
    if (libre(c, { ui: false })) {
      r.estado = "visible";
      puestas.push(c);
    } else r.estado = "punto";
  }

  // 4. los rótulos
  for (const it of discos) {
    const r = res.get(it.id);
    if (r.estado !== "visible" || !it.rotulo) continue;
    for (const lado of ["der", "izq"]) {
      const c = cajaRotulo(it, r, lado);
      if (cabe(c) && libre(c)) {
        r.rotulo = lado;
        puestas.push(c);
        break;
      }
    }
  }
  return res;
}

// Ancho de un rótulo "Cajamarca 21°/10°" en píxeles (aproximado: 7 px por letra más el relleno).
export const anchoRotulo = (texto) => 7 * texto.length + 26;
