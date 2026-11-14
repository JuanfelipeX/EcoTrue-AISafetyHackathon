// ECO · panel web. Sin dependencias externas: todo se dibuja con HTML y SVG.
"use strict";

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (t) => String(t ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
const pct = (x) => `${Math.round((x || 0) * 100)} %`;
const plural = (n, s, p) => `${n} ${n === 1 ? s : p}`;

const TIPOS = {
  organico: "Orgánico", literal: "Copia literal", parafrasis: "Paráfrasis", comunicado: "Comunicado",
  fabricado_literal: "Fabricado literal", fabricado_parafrasis: "Fabricado paráfrasis",
};
const TIPO_DESC = {
  organico: "Medios que reportan por su cuenta, con datos propios.",
  literal: "Un origen y copias casi idénticas.",
  parafrasis: "Un origen reescrito con otras palabras, sin datos nuevos.",
  comunicado: "Un comunicado oficial replicado por varios sitios.",
  fabricado_literal: "Copias casi idénticas que agregan detalles inventados (ataque).",
  fabricado_parafrasis: "Copias reescritas que además inventan detalles (ataque abierto).",
};
const METODOS = { linea_base: "Línea base", hechos: "ECO hechos", hibrido: "ECO híbrido" };
const SERIES = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)", "var(--s5)", "var(--s6)", "var(--s7)", "var(--s8)"];
const colorGrupo = (i) => SERIES[i] || "var(--tinta-3)";

const estado = { mundos: [], filtro: "", conjunto: "todos", mundo: null, metodo: "hibrido", modelo: "", resultados: null };

async function api(ruta, cuerpo) {
  const r = await fetch(ruta, cuerpo ? {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo),
  } : undefined);
  const datos = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(datos.detail ? (typeof datos.detail === "string" ? datos.detail : JSON.stringify(datos.detail)) : `Error ${r.status}`);
  return datos;
}

// ---------------- tooltip ----------------
const tip = $("#tooltip");
document.addEventListener("mousemove", (e) => {
  const el = e.target.closest?.("[data-tip]");
  if (!el) { tip.hidden = true; return; }
  tip.innerHTML = el.getAttribute("data-tip");
  tip.hidden = false;
  const w = tip.offsetWidth, h = tip.offsetHeight;
  let x = e.clientX + 14, y = e.clientY + 14;
  if (x + w > innerWidth - 8) x = e.clientX - w - 14;
  if (y + h > innerHeight - 8) y = e.clientY - h - 14;
  tip.style.left = `${x}px`; tip.style.top = `${y}px`;
});

// ---------------- tema y navegación ----------------
$("#tema").addEventListener("click", () => {
  const raiz = document.documentElement;
  const oscuro = raiz.dataset.theme ? raiz.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  raiz.dataset.theme = oscuro ? "light" : "dark";
  try { localStorage.setItem("eco-tema", raiz.dataset.theme); } catch (_) { /* sin almacenamiento */ }
});
try { const t = localStorage.getItem("eco-tema"); if (t) document.documentElement.dataset.theme = t; } catch (_) { /* nada */ }

function navegar() {
  const vista = (location.hash || "#laboratorio").slice(1);
  const valida = ["laboratorio", "resultados", "urls", "como", "instalar"].includes(vista) ? vista : "laboratorio";
  $$(".vista").forEach((v) => { v.hidden = v.id !== `vista-${valida}`; });
  $$(".pestanas a").forEach((a) => a.classList.toggle("activa", a.dataset.vista === valida));
  if (valida === "resultados") cargarResultados();
}
addEventListener("hashchange", navegar);

function segmentado(id, alCambiar) {
  $$(`#${id} button`).forEach((b) => b.addEventListener("click", () => {
    $$(`#${id} button`).forEach((x) => x.classList.toggle("activo", x === b));
    alCambiar(b.dataset.v);
  }));
}

// ---------------- modelos ----------------
async function cargarModelos() {
  const chip = $("#estado-modelo");
  try {
    const m = await api("/api/modelos");
    const vivos = Object.entries(m.proveedores).filter(([p, ok]) => ok && p !== "manual").map(([p]) => p);
    chip.innerHTML = `<span class="punto" style="background:${vivos.length ? "var(--bien)" : "var(--alerta)"}"></span>` +
      esc(`${m.principal} · respaldo: ${m.respaldo.join(", ")}`);
    chip.title = `Proveedores con credenciales o activos: ${vivos.join(", ") || "ninguno"} (más respuestas guardadas)`;
    const sel = $("#modelo");
    sel.innerHTML = `<option value="">Automático (cadena del .env)</option>` +
      m.sugeridos.map((x) => `<option value="${esc(x)}">${esc(x)}</option>`).join("");
  } catch (e) {
    chip.textContent = "API no disponible";
  }
}
$("#modelo").addEventListener("change", (e) => { estado.modelo = e.target.value; });

// ---------------- mundos ----------------
async function cargarMundos() {
  estado.mundos = await api("/api/mundos");
  pintarMundos();
}

function pintarMundos() {
  const f = estado.filtro.toLowerCase();
  const lista = estado.mundos.filter((m) =>
    (estado.conjunto === "todos" || m.conjunto === estado.conjunto) &&
    (!f || m.afirmacion.toLowerCase().includes(f) || m.id.includes(f)));
  $("#lista-mundos").innerHTML = lista.map((m) => `
    <li data-id="${esc(m.id)}" class="${estado.mundo?.id === m.id ? "activo" : ""}" tabindex="0">
      <div class="m-id"><span>${esc(m.id)} · ${m.paginas.length} páginas</span>
        <span class="etq ${m.conjunto}">${({ estres: "estrés", prueba: "prueba" })[m.conjunto] || "principal"}</span></div>
      <div class="m-af">${esc(m.afirmacion)}</div>
    </li>`).join("") || `<li class="vacia">Sin coincidencias.</li>`;
  $$("#lista-mundos li[data-id]").forEach((li) => {
    const elegir = () => seleccionarMundo(li.dataset.id);
    li.addEventListener("click", elegir);
    li.addEventListener("keydown", (e) => { if (e.key === "Enter") elegir(); });
  });
}

function seleccionarMundo(id) {
  estado.mundo = estado.mundos.find((m) => m.id === id);
  pintarMundos();
  $("#analizar").disabled = false;
  const m = estado.mundo;
  $("#resultado").innerHTML = `<div class="tarjeta">
    <h3 style="margin-top:0">Afirmación del mundo ${esc(m.id)}</h3>
    <p style="font-size:18px;font-weight:650;margin:0 0 10px">${esc(m.afirmacion)}</p>
    <p class="nota">Un buscador encontraría estas ${m.paginas.length} páginas. ¿Cuántas son fuentes de verdad?</p>
    <ul>${m.paginas.map((p) => `<li><b>${esc(p.medio)}</b> — <a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.titulo)}</a></li>`).join("")}</ul>
  </div>`;
  analizarMundo();
}

$("#filtro").addEventListener("input", (e) => { estado.filtro = e.target.value; pintarMundos(); });
segmentado("filtro-conjunto", (v) => { estado.conjunto = v; pintarMundos(); });
segmentado("metodo", (v) => { estado.metodo = v; if (estado.mundo) analizarMundo(); });
$("#analizar").addEventListener("click", () => analizarMundo());

// ---------------- carga con etapas ----------------
function mostrarCarga(contenedor, n, modelo) {
  const etapas = [
    `Cargando ${n} páginas y sus metadatos (fecha, sitio, enlaces)`,
    `Extrayendo hechos atómicos con ${modelo || "la cadena de modelos del .env"}`,
    "Aplicando la regla de independencia en orden cronológico",
  ];
  contenedor.innerHTML = `<div class="cargando"><h3>Analizando…</h3><ul class="etapas">
    ${etapas.map((t, i) => `<li data-i="${i}">${esc(t)}</li>`).join("")}</ul>
    <div class="cronometro">0 s</div></div>`;
  const inicio = Date.now();
  let etapa = 0;
  const marcar = () => $$(".etapas li", contenedor).forEach((li) => {
    const i = +li.dataset.i;
    li.className = i < etapa ? "hecha" : i === etapa ? "actual" : "";
  });
  marcar();
  const reloj = setInterval(() => {
    const s = Math.round((Date.now() - inicio) / 1000);
    const c = $(".cronometro", contenedor);
    if (c) c.textContent = `${s} s${s > 8 ? " · un modelo local puede tardar alrededor de un minuto; luego queda en caché" : ""}`;
    if (etapa === 0 && Date.now() - inicio > 600) { etapa = 1; marcar(); }
  }, 300);
  return () => clearInterval(reloj);
}

let peticionActual = 0;
async function analizarMundo() {
  const m = estado.mundo;
  if (!m) return;
  const id = ++peticionActual;
  const cont = $("#resultado");
  const parar = mostrarCarga(cont, m.paginas.length, estado.metodo === "linea_base" ? "— (sin LLM)" : estado.modelo);
  $("#analizar").disabled = true;
  try {
    const res = await api("/api/analizar_mundo", { mundo_id: m.id, metodo: estado.metodo, modelo: estado.modelo || null });
    if (id !== peticionActual) return;
    parar();
    cont.innerHTML = renderResultado(res, { comparar: true });
    enlazarVerdad(cont, res);
  } catch (e) {
    if (id !== peticionActual) return;
    parar();
    cont.innerHTML = `<div class="error">${esc(e.message)}</div>`;
  } finally {
    if (id === peticionActual) $("#analizar").disabled = false;
  }
}

// ---------------- normalización del resultado ----------------
function normalizar(res) {
  const docs = [...(res.documentos || [])].sort((a, b) => (a.fecha || "~").localeCompare(b.fecha || "~") || a.id.localeCompare(b.id));
  const grupos = [...(res.grupos || [])].sort((a, b) => (a.origen_fecha || "").localeCompare(b.origen_fecha || ""));
  const grupoDe = {}, padre = {};
  grupos.forEach((g, i) => {
    g.miembros.forEach((m) => { grupoDe[m] = i; });
    (g.derivaciones || []).forEach((d) => { padre[d.pagina] = d.deriva_de; });
  });
  const pag = {};
  (res.paginas || []).forEach((p) => { pag[p.id] = p; if (p.deriva_de) padre[p.id] = p.deriva_de; });
  const orden = {};
  docs.forEach((d, i) => { orden[d.id] = i; });
  const origenes = new Set(grupos.map((g) => g.origen));
  return { docs, grupos, grupoDe, padre, pag, orden, origenes };
}

function fechaCorta(iso, conDia = true) {
  if (!iso) return "sin fecha";
  const [d, t] = iso.slice(0, 16).split("T");
  const [, mes, dia] = d.split("-");
  return conDia ? `${dia}/${mes} ${t}` : t;
}

// ---------------- render principal ----------------
function renderResultado(res, { comparar = false } = {}) {
  const n = res.fuentes_aparentes, k = res.fuentes_efectivas;
  const nivel = k <= 1 && n > 1 ? "alerta" : k < n ? "medio" : "ok";
  const insignia = { alerta: "⚠ Un solo origen", medio: "◐ Parte es repetición", ok: "✓ Cobertura independiente" }[nivel];
  const N = normalizar(res);
  const modeloUsado = res.modelo ? `Hechos extraídos por <code>${esc(res.modelo)}</code>${res.desde_cache ? " (desde caché)" : ""}.` :
    res.metodo === "linea_base" ? "Sin LLM: solo similitud de texto y enlaces." : "";

  let html = `<div class="veredicto ${nivel}">
    <div class="cifras">
      <div class="cifra"><b>${n}</b><span>páginas</span></div>
      <div class="flecha" aria-hidden="true">→</div>
      <div class="cifra"><b>${k}</b><span>${k === 1 ? "fuente independiente" : "fuentes independientes"}</span></div>
    </div>
    <div>
      <span class="insignia ${nivel}">${insignia}</span>
      <div class="afirm">${esc(res.afirmacion)}</div>
      <p class="resumen">${esc(res.resumen)}</p>
      ${res.aviso ? `<div class="aviso">${esc(res.aviso)}</div>` : ""}
    </div>
  </div>`;

  if (comparar && res.linea_base) {
    html += `<div class="comparacion">
      <div class="comp"><div class="t">Fuentes aparentes</div><div class="v">${n}</div><div class="d">lo que cuenta un buscador</div></div>
      <div class="comp" data-cmp="base" data-k="${res.linea_base.fuentes_efectivas}"><div class="t">Línea base</div><div class="v">${res.linea_base.fuentes_efectivas}</div><div class="d">similitud de texto ≥ ${res.linea_base.umbral}</div></div>
      <div class="comp" data-cmp="eco" data-k="${k}"><div class="t">${esc(METODOS[res.metodo] || res.metodo)}</div><div class="v">${k}</div><div class="d">${res.metodo === "linea_base" ? "método seleccionado" : "hechos atómicos"}</div></div>
      <div class="comp verdad"><div class="t">Respuesta correcta</div><div class="v" data-verdad>?</div>
        <div class="d" data-verdad-d>guardada aparte del análisis</div><button class="boton-sec" data-revelar>Revelar</button></div>
    </div>`;
  }

  html += `<div class="tarjeta cascada"><h2>Árbol de origen: quién publicó primero y quién copió</h2>
    <p class="nota">Cada fila es una página, ordenada por hora de publicación. El color indica la fuente independiente de la que proviene.
      ${modeloUsado}</p>
    <div class="leyenda">${N.grupos.map((g, i) => `<span><i style="background:${colorGrupo(i)}"></i>Fuente ${i + 1}: ${esc(g.origen_sitio)}</span>`).join("")}
      <span><i class="hueco"></i>copia o derivada (sin datos propios)</span></div>
    <div class="cascada-scroll">${svgCascada(N)}</div></div>`;

  if (res.hechos && res.hechos.length) {
    html += `<div class="tarjeta"><h2>Matriz de hechos: qué aporta cada página</h2>
      <p class="nota">Columnas = páginas en orden cronológico (los números coinciden con el árbol). Una celda de color marca
        el primer lugar donde apareció un dato; azul claro, que solo lo repite. Una página sin celdas de color no aporta nada nuevo: por muy distinta que esté redactada, es eco.</p>
      <div class="leyenda"><span><i class="cuadro" style="background:var(--s1)"></i>dato nuevo (color de su fuente)</span>
        <span><i class="cuadro" style="background:var(--q1)"></i>repite un dato ya publicado</span>
        <span><i class="cuadro" style="background:var(--superficie-2)"></i>no lo menciona</span></div>
      <div class="matriz-scroll">${tablaHechos(res, N)}</div></div>`;

    html += `<div class="tarjeta"><h2>Qué se puede demostrar</h2>
      <div class="listas">
        <div><h3>Respaldado por 2 o más fuentes independientes</h3>${listaSimple(res.corroborados)}</div>
        <div><h3>Depende de una sola fuente</h3>${listaSimple(res.de_un_solo_origen)}</div>
      </div>
      ${res.atribuciones && res.atribuciones.length ? `<h3>No cuentan como aporte: frases sobre la noticia, no sobre el suceso</h3>
        <p class="nota" style="margin-top:0">Citar un comunicado o decir que algo es tendencia no es reportería propia.</p>${listaSimple(res.atribuciones)}` : ""}
      <p class="nota" style="margin-top:14px">ECO no dice si algo es verdad: mide cuánta evidencia independiente lo respalda.</p></div>`;
  }

  if (comparar && res.similitud && res.similitud.ids.length > 1) {
    html += `<div class="tarjeta"><h2>Lo que ve la línea base: similitud de texto entre páginas</h2>
      <p class="nota">La línea base une dos páginas si su similitud supera ${res.linea_base.umbral} (celdas con borde).
        Una paráfrasis hecha con IA baja la similitud y se escapa; dos medios que cubren el mismo hecho la suben y se fusionan por error.</p>
      ${tablaSimilitud(res, N)}</div>`;
  }
  return html;
}

function listaSimple(items) {
  if (!items || !items.length) return `<p class="vacia">Ninguno.</p>`;
  return `<ul>${items.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>`;
}

// ---------------- árbol de origen (SVG) ----------------
function svgCascada(N) {
  const docs = N.docs;
  const W = 960, izq = 300, der = 40, arriba = 34, filaH = 50;
  const H = arriba + docs.length * filaH + 10;
  const tiempos = docs.map((d) => (d.fecha ? Date.parse(d.fecha) : NaN)).filter((t) => !isNaN(t));
  const tmin = Math.min(...tiempos), tmax = Math.max(...tiempos);
  const x = (iso) => {
    const t = Date.parse(iso);
    if (isNaN(t) || tmax === tmin) return izq + (W - izq - der) / 2;
    return izq + 12 + ((t - tmin) / (tmax - tmin)) * (W - izq - der - 24);
  };
  const y = (i) => arriba + i * filaH + filaH / 2;
  const mismoDia = tiempos.length && new Date(tmin).toDateString() === new Date(tmax).toDateString();

  // eje de tiempo
  let eje = "";
  if (tiempos.length && tmax > tmin) {
    for (let i = 0; i <= 4; i++) {
      const t = tmin + ((tmax - tmin) * i) / 4;
      const xi = izq + 12 + (i / 4) * (W - izq - der - 24);
      const f = new Date(t);
      const hh = `${String(f.getHours()).padStart(2, "0")}:${String(f.getMinutes()).padStart(2, "0")}`;
      const etq = mismoDia ? hh : `${String(f.getDate()).padStart(2, "0")}/${String(f.getMonth() + 1).padStart(2, "0")} ${hh}`;
      eje += `<line class="rejilla" x1="${xi}" x2="${xi}" y1="${arriba - 6}" y2="${H - 6}"/>
        <text x="${xi}" y="${arriba - 12}" text-anchor="middle">${esc(etq)}</text>`;
    }
  }

  let filas = "", aristas = "", nodos = "";
  docs.forEach((d, i) => {
    const g = N.grupoDe[d.id] ?? 0;
    const color = colorGrupo(g);
    const p = N.pag[d.id];
    const esOrigen = N.origenes.has(d.id);
    const madre = N.padre[d.id];
    const nombreMadre = madre ? (docs.find((x) => x.id === madre)?.sitio || madre) : "";
    let sub;
    if (esOrigen) sub = i === 0 ? "primera publicación" : (p ? `fuente propia · ${plural(p.hechos_nuevos.length, "dato nuevo", "datos nuevos")}` : "fuente propia");
    else sub = `deriva de ${nombreMadre}`;
    const motivo = p?.motivo ? `<br>${esc(p.motivo)}` : "";
    const tipHtml = `<b>${esc(d.sitio)}</b><br>${esc(fechaCorta(d.fecha))} · ${esc(d.dominio || "")}<br>` +
      (esOrigen ? `Fuente independiente ${g + 1}` : `Copia o derivada de ${esc(nombreMadre)}`) + motivo +
      (p ? `<br>Datos en la página: ${p.hechos.length} · nuevos: ${p.hechos_nuevos.length}` : "") +
      (d.titulo ? `<br><i>${esc(d.titulo)}</i>` : "");
    const etiquetaSitio = d.sitio.length > 30 ? d.sitio.slice(0, 29) + "…" : d.sitio;
    filas += `<g class="fila" data-tip="${esc(tipHtml)}">
      <rect class="fila-fondo" x="0" y="${y(i) - filaH / 2 + 2}" width="${W}" height="${filaH - 4}" rx="8"/>
      <text x="14" y="${y(i) - 3}" class="sub" font-weight="700">${i + 1}</text>
      <a href="${esc(d.url)}" target="_blank" rel="noopener"><text x="34" y="${y(i) - 3}" class="sitio">${esc(etiquetaSitio)}</text></a>
      <text x="34" y="${y(i) + 14}" class="sub">${esc(fechaCorta(d.fecha, !mismoDia))} · ${esc(sub)}</text>
    </g>`;
    if (madre && N.orden[madre] !== undefined) {
      const j = N.orden[madre];
      const x1 = x(docs[j].fecha), y1 = y(j), x2 = x(d.fecha), y2 = y(i);
      aristas += `<path class="arista" stroke="${color}" d="M${x1},${y1} C${x1},${(y1 + y2) / 2} ${x2},${(y1 + y2) / 2 - 6} ${x2},${y2 - 9}"/>`;
    }
    const cx = x(d.fecha), cy = y(i);
    nodos += esOrigen
      ? `<circle class="nodo-borde" cx="${cx}" cy="${cy}" r="10" fill="${color}" pointer-events="none"/>`
      : `<circle cx="${cx}" cy="${cy}" r="7" fill="var(--superficie)" stroke="${color}" stroke-width="2.5" pointer-events="none"/>`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Árbol de origen de las páginas">
    <g class="eje">${eje}</g>${filas}<g pointer-events="none">${aristas}</g>${nodos}</svg>`;
}

// ---------------- matriz de hechos ----------------
function tablaHechos(res, N) {
  const docs = N.docs;
  const cab = docs.map((d, i) => {
    const g = N.grupoDe[d.id] ?? 0, origen = N.origenes.has(d.id);
    return `<th class="col" data-tip="${esc(`<b>${esc(d.sitio)}</b><br>${esc(fechaCorta(d.fecha))}<br>${origen ? "fuente independiente" : "copia o derivada"}`)}">
      <span class="num ${origen ? "" : "hueco"}" style="${origen ? `background:${colorGrupo(g)}` : `border-color:${colorGrupo(g)}`}">${i + 1}</span></th>`;
  }).join("");
  const hechos = [...res.hechos].sort((a, b) => b.fuentes_independientes - a.fuentes_independientes || a.id.localeCompare(b.id, undefined, { numeric: true }));
  const filaDe = (h) => {
    const celdas = docs.map((d) => {
      const tiene = h.paginas.includes(d.id);
      const nuevo = tiene && N.pag[d.id]?.hechos_nuevos?.includes(h.id);
      const g = N.grupoDe[d.id] ?? 0;
      const t = `<b>${esc(d.sitio)}</b><br>${tiene ? (nuevo ? "Publica este dato por primera vez" : "Repite un dato ya publicado") : "No menciona este dato"}<br><i>${esc(h.texto)}</i>`;
      return `<td class="celda ${tiene ? (nuevo ? "nuevo" : "repite") : ""}" style="${nuevo ? `background:${colorGrupo(g)}` : ""}" data-tip="${esc(t)}">${nuevo ? "+" : ""}</td>`;
    }).join("");
    return `<tr><td class="hecho">${esc(h.texto)}</td>${celdas}
      <td class="n"><b>${h.fuentes_independientes}</b> ${h.fuentes_independientes === 1 ? "fuente" : "fuentes"}</td></tr>`;
  };
  const corro = hechos.filter((h) => h.fuentes_independientes >= 2);
  const solos = hechos.filter((h) => h.fuentes_independientes < 2);
  const span = docs.length + 2;
  return `<table class="matriz"><thead><tr><th style="text-align:left">Hecho atómico</th>${cab}<th></th></tr></thead><tbody>
    ${corro.length ? `<tr class="sep"><td colspan="${span}">Corroborados por fuentes independientes</td></tr>${corro.map(filaDe).join("")}` : ""}
    ${solos.length ? `<tr class="sep"><td colspan="${span}">Dependen de una sola fuente</td></tr>${solos.map(filaDe).join("")}` : ""}
  </tbody></table>`;
}

// ---------------- similitud ----------------
function tablaSimilitud(res, N) {
  const { ids, matriz } = res.similitud;
  const umbral = res.linea_base.umbral;
  const idx = ids.map((id, i) => ({ id, i })).sort((a, b) => (N.orden[a.id] ?? 0) - (N.orden[b.id] ?? 0));
  const escala = ["--q0", "--q1", "--q2", "--q3", "--q4", "--q5", "--q6"];
  const color = (v) => `var(${escala[Math.min(6, Math.max(0, Math.floor(v * 7)))]})`;
  const ink = (v) => (v >= 0.55 ? "#fff" : "var(--tinta-2)");
  const nombre = (id) => N.docs.find((d) => d.id === id)?.sitio || id;
  let html = `<div class="matriz-scroll"><table class="heatmap"><tr><th></th>${idx.map((a) => `<th>${(N.orden[a.id] ?? 0) + 1}</th>`).join("")}</tr>`;
  idx.forEach((a) => {
    html += `<tr><th>${(N.orden[a.id] ?? 0) + 1}</th>` + idx.map((b) => {
      const v = matriz[a.i][b.i];
      if (a.id === b.id) return `<td style="background:var(--superficie-2)"></td>`;
      return `<td class="${v >= umbral ? "sobre" : ""}" style="background:${color(v)};color:${ink(v)}"
        data-tip="${esc(`<b>${esc(nombre(a.id))}</b> vs <b>${esc(nombre(b.id))}</b><br>similitud ${v.toFixed(2)} ${v >= umbral ? "· la línea base las une" : "· la línea base las separa"}`)}">${v.toFixed(2).slice(1)}</td>`;
    }).join("") + "</tr>";
  });
  return html + "</table></div>";
}

// ---------------- revelar respuesta ----------------
function enlazarVerdad(cont, res) {
  const boton = $("[data-revelar]", cont);
  if (!boton) return;
  boton.addEventListener("click", async () => {
    boton.disabled = true;
    try {
      const v = await api(`/api/mundos/${encodeURIComponent(res.mundo)}/verdad`);
      const esperado = v.fuentes_efectivas_esperadas;
      $("[data-verdad]", cont).textContent = esperado;
      $("[data-verdad-d]", cont).innerHTML = `<b>${esc(TIPOS[v.tipo] || v.tipo)}</b>: ${esc(TIPO_DESC[v.tipo] || "")}`;
      boton.remove();
      $$("[data-cmp]", cont).forEach((c) => {
        const ok = +c.dataset.k === esperado;
        c.querySelector(".d").insertAdjacentHTML("beforeend",
          ok ? ` · <span class="marca-ok">✓ acierta</span>` : ` · <span class="marca-mal">✗ falla</span>`);
      });
    } catch (e) {
      boton.textContent = "No disponible";
    }
  });
}

// ---------------- analizar URLs ----------------
$("#ejemplo-urls").addEventListener("click", () => {
  const m = estado.mundos.find((x) => x.id === "e01-s1") || estado.mundos[0];
  if (!m) return;
  $("#afirmacion").value = m.afirmacion;
  $("#urls").value = m.paginas.map((p) => p.url).join("\n");
});
$("#form-urls").addEventListener("submit", async (e) => {
  e.preventDefault();
  const urls = $("#urls").value.split(/\s+/).map((u) => u.trim()).filter(Boolean);
  const cont = $("#resultado-urls");
  const parar = mostrarCarga(cont, urls.length, estado.modelo);
  try {
    const res = await api("/api/analizar", { afirmacion: $("#afirmacion").value.trim(), urls, metodo: estado.metodo, modelo: estado.modelo || null });
    parar();
    const errores = (res.urls_con_error || []).map((x) => `<li>${esc(x.url)}: ${esc(x.error)}</li>`).join("");
    cont.innerHTML = renderResultado(res) + (errores ? `<div class="tarjeta"><h2>URLs que no se pudieron leer</h2><ul>${errores}</ul></div>` : "");
  } catch (err) {
    parar();
    cont.innerHTML = `<div class="error">${esc(err.message)}</div>`;
  }
});

// ---------------- resultados ----------------
async function cargarResultados() {
  if (estado.resultados) return;
  try {
    estado.resultados = await api("/api/resultados");
  } catch (e) {
    $("#kpis").innerHTML = `<div class="error">${esc(e.message)}</div>`;
    return;
  }
  const comps = estado.resultados.comparaciones;
  const sel = $("#sel-evaluacion");
  const etiqueta = (c) => `${c.modelo} · ${c.conjunto === "prueba" ? "conjunto de PRUEBA retenido (18 mundos)" : "conjunto de desarrollo (36 mundos)"}`;
  sel.innerHTML = comps.map((c, i) => `<option value="${i}">${esc(etiqueta(c))}</option>`).join("");
  let real = comps.findIndex((c) => c.modelo.includes("sonnet") && c.conjunto === "prueba");
  if (real < 0) real = comps.findIndex((c) => !c.modelo.startsWith("manual/"));
  sel.value = String(real >= 0 ? real : 0);
  sel.onchange = pintarResultados;
  pintarResultados();
  pintarBarrido();
  pintarAgente();
}

$("#ver-tabla").addEventListener("click", () => {
  const t = $("#tabla-tipos"), g = $("#grafico-tipos");
  t.hidden = !t.hidden; g.hidden = !t.hidden ? true : false;
  $("#ver-tabla").textContent = t.hidden ? "Ver como tabla" : "Ver como gráfico";
});

function global(res, metodo, tipos) {
  const sub = tipos.map((t) => res[metodo]?.[t]).filter(Boolean);
  const n = sub.reduce((s, r) => s + r.n, 0);
  return n ? sub.reduce((s, r) => s + r.exactitud * r.n, 0) / n : null;
}

function pintarResultados() {
  const comps = estado.resultados.comparaciones;
  if (!comps.length) {
    $("#kpis").innerHTML = `<div class="error">Aún no hay evaluaciones. Corre <code>python -m evaluacion.evaluar --modelo ...</code></div>`;
    return;
  }
  const c = comps[+$("#sel-evaluacion").value];
  const r = c.resumenes;
  const principal = ["organico", "literal", "parafrasis", "comunicado"];
  const estres = ["fabricado_literal", "fabricado_parafrasis"];
  const kp = (t, v, d) => `<div class="kpi"><div class="t">${t}</div><div class="v">${v == null ? "—" : pct(v)}</div><div class="d">${d}</div></div>`;
  const nP = principal.reduce((s, t) => s + (r.linea_base?.[t]?.n || 0), 0);
  const nE = estres.reduce((s, t) => s + (r.linea_base?.[t]?.n || 0), 0);
  $("#kpis").innerHTML =
    kp("Línea base · principal", global(r, "linea_base", principal), `${nP} mundos · solo similitud de texto`) +
    kp("ECO híbrido · principal", global(r, "hibrido", principal), `${nP} mundos · hechos atómicos + guardia`) +
    kp("ECO híbrido · estrés", global(r, "hibrido", estres), `${nE} mundos con copias que inventan detalles`) +
    kp("Fusión falsa en orgánico", r.hibrido?.organico?.fusion_falsa, "medios independientes que ECO juntó por error");

  const tipos = Object.keys(TIPOS).filter((t) => r.linea_base?.[t]);
  const metodos = ["linea_base", "hechos", "hibrido"];
  $("#grafico-tipos").innerHTML = graficoBarras(tipos, metodos, (t, m) => r[m]?.[t]?.exactitud ?? 0,
    (t, m) => `<b>${esc(METODOS[m])}</b> · ${esc(TIPOS[t])}<br>Exactitud ${pct(r[m]?.[t]?.exactitud)} (n = ${r[m]?.[t]?.n})<br>Error medio en el conteo: ${(r[m]?.[t]?.error_medio ?? 0).toFixed(2)}`);
  $("#tabla-tipos").innerHTML = `<table class="tabla"><thead><tr><th>Tipo</th><th>n</th>${metodos.map((m) => `<th>${METODOS[m]}</th>`).join("")}</tr></thead><tbody>
    ${tipos.map((t) => `<tr><td>${esc(TIPOS[t])}</td><td>${r.linea_base[t].n}</td>${metodos.map((m) => `<td>${pct(r[m]?.[t]?.exactitud)}</td>`).join("")}</tr>`).join("")}
    <tr><td><b>Global principal</b></td><td>${nP}</td>${metodos.map((m) => `<td><b>${pct(global(r, m, principal))}</b></td>`).join("")}</tr>
    <tr><td><b>Global estrés</b></td><td>${nE}</td>${metodos.map((m) => `<td><b>${pct(global(r, m, estres))}</b></td>`).join("")}</tr>
    </tbody></table>${c.errores ? `<p class="nota">${c.errores} mundos con error del LLM quedaron fuera.</p>` : ""}`;
}

function graficoBarras(categorias, series, valor, tipHtml) {
  const W = 960, H = 320, izq = 44, der = 12, arriba = 16, abajo = 46;
  const ancho = W - izq - der, alto = H - arriba - abajo;
  const bandaW = ancho / categorias.length;
  const barW = Math.min(34, (bandaW - 28) / series.length);
  const yv = (v) => arriba + alto - v * alto;
  let g = "";
  [0, .25, .5, .75, 1].forEach((v) => {
    g += `<line class="rej" x1="${izq}" x2="${W - der}" y1="${yv(v)}" y2="${yv(v)}"/><text x="${izq - 8}" y="${yv(v) + 4}" text-anchor="end">${v * 100}%</text>`;
  });
  let barras = "";
  categorias.forEach((c, ci) => {
    const x0 = izq + ci * bandaW + (bandaW - barW * series.length - 2 * (series.length - 1)) / 2;
    series.forEach((s, si) => {
      const v = valor(c, s), x = x0 + si * (barW + 2), y = yv(v), h = Math.max(0, arriba + alto - y);
      const r = Math.min(4, h);
      const d = h > 0 ? `M${x},${y + h} V${y + r} Q${x},${y} ${x + r},${y} H${x + barW - r} Q${x + barW},${y} ${x + barW},${y + r} V${y + h} Z` : "";
      barras += `<path d="${d}" fill="${SERIES[si]}"/>`;
      barras += `<rect class="golpe" x="${x - 1}" y="${arriba}" width="${barW + 2}" height="${alto}" data-tip="${esc(tipHtml(c, s))}"/>`;
      if (v < 0.999) barras += `<text class="etq-v" x="${x + barW / 2}" y="${y - 5}" text-anchor="middle">${Math.round(v * 100)}</text>`;
    });
    barras += `<text class="etq-x" x="${izq + ci * bandaW + bandaW / 2}" y="${H - abajo + 20}" text-anchor="middle">${esc(TIPOS[c] || c)}</text>`;
  });
  // separador entre conjunto principal y estrés
  const corte = categorias.findIndex((c) => c.startsWith("fabricado"));
  if (corte > 0) {
    const xs = izq + corte * bandaW;
    barras += `<line x1="${xs}" x2="${xs}" y1="${arriba}" y2="${H - abajo + 32}" stroke="var(--tinta-3)" stroke-dasharray="3 4"/>
      <text class="etq-v" x="${xs + 8}" y="${H - 6}">conjunto de estrés (ataques) →</text>
      <text class="etq-v" x="${xs - 8}" y="${H - 6}" text-anchor="end">← conjunto principal</text>`;
  }
  const leyenda = `<div class="leyenda">${series.map((s, i) => `<span><i class="cuadro" style="background:${SERIES[i]}"></i>${esc(METODOS[s] || s)}</span>`).join("")}<span>· los números marcan barras por debajo de 100 %</span></div>`;
  return `${leyenda}<div class="grafico"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Exactitud por tipo y método">
    <g class="eje">${g}</g><line class="base" x1="${izq}" x2="${W - der}" y1="${arriba + alto}" y2="${arriba + alto}"/>${barras}</svg></div>`;
}

function pintarBarrido() {
  const b = estado.resultados.barrido_linea_base;
  const cont = $("#grafico-barrido");
  if (!b) { cont.innerHTML = `<p class="vacia">Sin datos: corre <code>python -m evaluacion.evaluar_linea_base --barrido</code>.</p>`; return; }
  const umbrales = Object.keys(b).map(Number).sort((a, c) => a - c);
  const lineas = [["organico", "Orgánico (no fusionar medios)"], ["parafrasis", "Paráfrasis (unir copias)"]];
  const W = 460, H = 260, izq = 40, der = 16, arriba = 14, abajo = 34;
  const xv = (u) => izq + ((u - umbrales[0]) / (umbrales.at(-1) - umbrales[0])) * (W - izq - der);
  const yv = (v) => arriba + (1 - v) * (H - arriba - abajo);
  let g = "";
  [0, .5, 1].forEach((v) => { g += `<line class="rej" x1="${izq}" x2="${W - der}" y1="${yv(v)}" y2="${yv(v)}"/><text x="${izq - 6}" y="${yv(v) + 4}" text-anchor="end">${v * 100}%</text>`; });
  umbrales.forEach((u) => { g += `<text x="${xv(u)}" y="${H - abajo + 18}" text-anchor="middle">${u.toFixed(1)}</text>`; });
  let trazos = "";
  lineas.forEach(([t], i) => {
    const pts = umbrales.map((u) => `${xv(u)},${yv(b[u.toFixed(1)]?.[t]?.exactitud ?? b[String(u)]?.[t]?.exactitud ?? 0)}`);
    trazos += `<polyline points="${pts.join(" ")}" fill="none" stroke="${SERIES[i]}" stroke-width="2" stroke-linejoin="round"/>`;
    umbrales.forEach((u) => {
      const v = b[u.toFixed(1)]?.[t]?.exactitud ?? 0;
      trazos += `<circle cx="${xv(u)}" cy="${yv(v)}" r="4" fill="${SERIES[i]}" stroke="var(--superficie)" stroke-width="2"/>`;
    });
  });
  let golpes = "";
  umbrales.forEach((u, i) => {
    const x0 = i === 0 ? izq : (xv(umbrales[i - 1]) + xv(u)) / 2;
    const x1 = i === umbrales.length - 1 ? W - der : (xv(u) + xv(umbrales[i + 1])) / 2;
    const fila = b[u.toFixed(1)] || {};
    golpes += `<rect class="golpe" x="${x0}" y="${arriba}" width="${x1 - x0}" height="${H - arriba - abajo}"
      data-tip="${esc(`<b>Umbral ${u.toFixed(1)}</b><br>Orgánico: ${pct(fila.organico?.exactitud)}<br>Paráfrasis: ${pct(fila.parafrasis?.exactitud)}`)}"/>`;
  });
  const actual = 0.6;
  const marca = umbrales.includes(actual) ? `<line x1="${xv(actual)}" x2="${xv(actual)}" y1="${arriba}" y2="${H - abajo}" stroke="var(--tinta-3)" stroke-dasharray="3 4"/>
    <text class="etq-v" x="${xv(actual) + 6}" y="${H - abajo - 8}">umbral usado (0.6)</text>` : "";
  cont.innerHTML = `<div class="leyenda">${lineas.map(([, n], i) => `<span><i style="background:${SERIES[i]}"></i>${esc(n)}</span>`).join("")}</div>
    <div class="grafico"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Exactitud de la línea base por umbral">
    <g class="eje">${g}</g>${marca}${trazos}${golpes}
    <text class="etq-v" x="${(W + izq) / 2}" y="${H - 2}" text-anchor="middle">umbral de similitud</text></svg></div>`;
}

function pintarAgente() {
  const agentes = estado.resultados.agentes;
  const cont = $("#grafico-agente");
  if (!agentes.length) {
    cont.innerHTML = `<p class="vacia">Aún no hay corridas. Corre <code>python -m demo.agente --modelo ...</code>.</p>`;
    return;
  }
  const a = agentes[agentes.length - 1];
  const f = a.filas;
  const unOrigen = f.filter((x) => x.esperado === "una_sola_fuente");
  const org = f.filter((x) => x.esperado === "confirmado_por_varias_fuentes");
  const tasa = (sub, modo, nivel) => (sub.length ? sub.filter((x) => x[modo] === nivel).length / sub.length : 0);
  const metricas = [
    ["Dice “confirmado” con un solo origen", unOrigen, "confirmado_por_varias_fuentes", "menos es mejor"],
    ["Reconoce que hay un solo origen", unOrigen, "una_sola_fuente", "más es mejor"],
    ["Reconoce cobertura independiente", org, "confirmado_por_varias_fuentes", "más es mejor"],
  ];
  const W = 460, filaH = 64, izq = 10, H = metricas.length * filaH + 10;
  const ancho = W - izq - 60;
  let svg = "";
  metricas.forEach(([nombre, sub, nivel, dir], i) => {
    const y0 = i * filaH + 6;
    svg += `<text class="etq-x" x="${izq}" y="${y0 + 10}">${esc(nombre)} <tspan class="etq-v">(${dir}, n = ${sub.length})</tspan></text>`;
    ["sin_eco", "con_eco"].forEach((modo, j) => {
      const v = tasa(sub, modo, nivel), y = y0 + 18 + j * 18, w = Math.max(2, v * ancho);
      svg += `<path d="M${izq},${y} H${izq + w - 4} Q${izq + w},${y} ${izq + w},${y + 4} V${y + 10} Q${izq + w},${y + 14} ${izq + w - 4},${y + 14} H${izq} Z" fill="${SERIES[j]}"/>
        <text class="etq-v" x="${izq + w + 6}" y="${y + 11}">${pct(v)}</text>
        <rect class="golpe" x="${izq}" y="${y - 2}" width="${ancho + 50}" height="18" data-tip="${esc(`<b>${modo === "sin_eco" ? "Sin ECO" : "Con ECO"}</b><br>${esc(nombre)}: ${pct(v)}`)}"/>`;
    });
  });
  cont.innerHTML = `<div class="leyenda"><span><i class="cuadro" style="background:${SERIES[0]}"></i>Sin ECO</span>
    <span><i class="cuadro" style="background:${SERIES[1]}"></i>Con ECO</span><span>· agente: <code>${esc(a.modelo)}</code>, ${f.length} mundos</span></div>
    <div class="grafico"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Agente sin ECO y con ECO">${svg}</svg></div>`;

  const nivelTxt = { confirmado_por_varias_fuentes: "confirmado por varias fuentes", una_sola_fuente: "una sola fuente", no_se_puede_determinar: "no se puede determinar" };
  const ejemplos = f.filter((x) => x.sin_eco !== x.con_eco && x.con_eco === x.esperado).slice(0, 4);
  if (ejemplos.length) {
    $("#ejemplos-agente-wrap").hidden = false;
    $("#ejemplos-agente").innerHTML = ejemplos.map((x) => `<div class="ejemplo">
      <div><b>${esc(x.mundo)}</b><br><span class="nota">${esc(TIPOS[x.tipo] || x.tipo)} · ECO: ${x.eco_fuentes} ${x.eco_fuentes === 1 ? "fuente" : "fuentes"}</span></div>
      <div class="lado"><span class="etq">Sin ECO · ${esc(nivelTxt[x.sin_eco] || x.sin_eco)}</span><div>${esc(x.sin_eco_respuesta)}</div></div>
      <div class="lado"><span class="etq">Con ECO · ${esc(nivelTxt[x.con_eco] || x.con_eco)}</span><div>${esc(x.con_eco_respuesta)}</div></div>
    </div>`).join("");
  }
}

// ---------------- inicio ----------------
// ---------------- Instalar: direcciones de este servidor y botones de copiar ----------------
function prepararInstalar() {
  const origen = location.origin;
  const mcp = `${origen}/mcp`;
  $$(".origen").forEach((e) => { e.textContent = origen; });
  $$(".origen-mcp").forEach((e) => { e.textContent = mcp; });
  $$("[data-plantilla]").forEach((e) => { e.textContent = e.dataset.plantilla.replaceAll("{MCP}", mcp); });
  $$("[data-copiar-origen]").forEach((b) => { b.dataset.copiar = origen + b.dataset.copiarOrigen; });
  document.addEventListener("click", async (ev) => {
    const ir = ev.target.closest("[data-ir]");
    if (ir) {
      ev.preventDefault();
      document.getElementById(ir.dataset.ir)?.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    const boton = ev.target.closest(".copiar");
    if (!boton) return;
    const texto = boton.dataset.copiar ?? boton.parentElement.querySelector("pre, code")?.textContent ?? "";
    try {
      await navigator.clipboard.writeText(texto);
      boton.textContent = "Copiado ✓";
    } catch (_) {
      boton.textContent = "Selecciona y copia";
    }
    setTimeout(() => { boton.textContent = "Copiar"; }, 1600);
  });
}
prepararInstalar();
navegar();
cargarModelos();
cargarMundos().then(() => {
  const inicial = new URLSearchParams(location.search).get("mundo");
  if (inicial) seleccionarMundo(inicial);
}).catch((e) => { $("#lista-mundos").innerHTML = `<li class="error">${esc(e.message)}</li>`; });
