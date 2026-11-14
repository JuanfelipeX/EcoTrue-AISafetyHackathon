// Popup de ECO: analizar la pestaña actual, elegir con qué compararla y ajustar modelo, tema y servidor.

const $ = (s) => document.querySelector(s);
const esc = (t) => ecoEsc(t);
const COLORES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];
const PRUEBA = new URLSearchParams(location.search).get("url"); // ?url=… abre el popup como pestaña para probarlo
let pestanaActual = null;
let modelos = [];

async function leer(clave, defecto) {
  try { return (await chrome.storage.local.get(clave))[clave] ?? defecto; } catch (_) { return defecto; }
}
async function guardar(clave, valor) {
  try { await chrome.storage.local.set({ [clave]: valor }); } catch (_) { /* sin almacenamiento */ }
}

// ---------------- tema ----------------
async function aplicarTema(tema) {
  document.documentElement.dataset.tema = tema === "auto" ? "" : tema;
  document.querySelectorAll("#temas button").forEach((b) => b.classList.toggle("activo", b.dataset.tema === tema));
}
document.querySelectorAll("#temas button").forEach((b) => b.addEventListener("click", async () => {
  await guardar("ecoTema", b.dataset.tema);
  aplicarTema(b.dataset.tema);
}));

// ---------------- vistas ----------------
function mostrarVista(nombre) {
  $("#vista-principal").hidden = nombre !== "principal";
  $("#vista-ajustes").hidden = nombre !== "ajustes";
}
$("#ir-ajustes").addEventListener("click", () => mostrarVista($("#vista-ajustes").hidden ? "ajustes" : "principal"));
$("#volver").addEventListener("click", () => mostrarVista("principal"));

// ---------------- pestañas para comparar ----------------
const PALABRAS_VACIAS = new Set("de la el los las un una y o en por para con del al que se su sus es son a lo como más tras sobre news noticias".split(" "));
function palabras(t) {
  return new Set((t || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").split(/[^a-z0-9ñ]+/)
    .filter((w) => w.length > 3 && !PALABRAS_VACIAS.has(w)));
}

function filaInterruptor(url, titulo, marcado) {
  let host = url;
  try { host = new URL(url).hostname.replace(/^www\./, ""); } catch (_) { /* url rara */ }
  const li = document.createElement("li");
  li.innerHTML = `<div class="texto"><b title="${esc(titulo)}">${esc(titulo || host)}</b><small>${esc(host)}</small></div>
    <label class="interruptor"><input type="checkbox" value="${esc(url)}" ${marcado ? "checked" : ""}><span></span></label>`;
  return li;
}

async function listarPestanas() {
  const lista = $("#lista-pestanas");
  if (PRUEBA) { lista.innerHTML = `<li class="vacia">Modo de prueba.</li>`; return; }
  const todas = await chrome.tabs.query({ currentWindow: true });
  const otras = todas.filter((t) => t.id !== pestanaActual?.id && /^https?:/.test(t.url || ""));
  if (!otras.length) {
    lista.innerHTML = `<li class="vacia">Abre en otras pestañas notas del mismo tema para compararlas, o pega su URL abajo.</li>`;
    return;
  }
  const base = palabras(pestanaActual?.title);
  lista.innerHTML = "";
  otras.slice(0, 15).forEach((t) => {
    const comunes = [...palabras(t.title)].filter((w) => base.has(w)).length;
    lista.appendChild(filaInterruptor(t.url, t.title, comunes >= 2));
  });
}

$("#agregar-url").addEventListener("click", () => {
  const campo = $("#url-extra");
  const url = campo.value.trim();
  if (!/^https?:\/\//.test(url)) { campo.focus(); return; }
  const lista = $("#lista-pestanas");
  lista.querySelector(".vacia")?.remove();
  lista.prepend(filaInterruptor(url, "URL agregada", true));
  campo.value = "";
});
$("#url-extra").addEventListener("keydown", (e) => { if (e.key === "Enter") $("#agregar-url").click(); });

// ---------------- modelos ----------------
async function cargarModelos() {
  const api = await ecoApi();
  try {
    const r = await fetch(`${api}/api/modelos`);
    modelos = (await r.json()).para_clientes || [];
  } catch (_) {
    modelos = [];
  }
  const elegido = await leer("ecoModelo", "");
  const caja = $("#modelos");
  const opciones = [{ id: "", etiqueta: "Automático", detalle: "El servidor elige: el modelo principal y, si falla, el de respaldo." }, ...modelos];
  caja.innerHTML = opciones.map((m) => `<button data-id="${esc(m.id)}" class="${m.id === elegido ? "activo" : ""}">${esc(m.etiqueta)}</button>`).join("");
  const pintarDetalle = (id) => {
    const m = opciones.find((x) => x.id === id) || opciones[0];
    $("#detalle-modelo").textContent = m.detalle + (m.id ? ` (${m.id.split("/").pop()})` : "");
    $("#pista-modelo").textContent = `Modelo: ${m.etiqueta}${m.id ? "" : " (servidor)"} · se cambia en ⚙`;
  };
  pintarDetalle(elegido);
  caja.querySelectorAll("button").forEach((b) => b.addEventListener("click", async () => {
    caja.querySelectorAll("button").forEach((x) => x.classList.toggle("activo", x === b));
    await guardar("ecoModelo", b.dataset.id);
    pintarDetalle(b.dataset.id);
  }));
}

// ---------------- servidor ----------------
async function prepararServidor() {
  const api = await ecoApi();
  $("#servidor").value = api;
  $("#abrir-panel").href = `${api}/`;
  $("#abrir-instalar").href = `${api}/#instalar`;
  $("#guardar-servidor").addEventListener("click", async () => {
    const valor = $("#servidor").value.trim().replace(/\/+$/, "") || ECO_API_DEFECTO;
    $("#estado-servidor").textContent = "Probando…";
    const vivo = await ecoVivo(valor);
    await guardar("ecoApi", valor);
    $("#estado-servidor").textContent = vivo ? "Guardado: el servidor responde." : "Guardado, pero no responde. Revisa la dirección.";
    cargarModelos();
  });
}

// ---------------- resultado ----------------
function arco(fraccion, color) {
  // Semicírculo: lleno según fuentes independientes / páginas.
  const r = 46, cx = 55, cy = 58, largo = Math.PI * r;
  const lleno = Math.max(0.04, Math.min(1, fraccion)) * largo;
  return `<svg viewBox="0 0 110 66" aria-hidden="true">
    <path class="pista-arco" d="M${cx - r} ${cy} A${r} ${r} 0 0 1 ${cx + r} ${cy}" fill="none" stroke-width="11" stroke-linecap="round"/>
    <path d="M${cx - r} ${cy} A${r} ${r} 0 0 1 ${cx + r} ${cy}" fill="none" stroke="${color}" stroke-width="11" stroke-linecap="round"
      stroke-dasharray="${lleno} ${largo}"/></svg>`;
}

function pintarResultado(d, api) {
  const n = d.fuentes_aparentes, k = d.fuentes_efectivas;
  const nivel = n <= 1 ? "medio" : k <= 1 ? "alerta" : k < n ? "medio" : "ok";
  const color = { alerta: "var(--mal)", medio: "var(--medio)", ok: "var(--bien)" }[nivel];
  const texto = n <= 1 ? "Solo una página" : { alerta: "Un solo origen", medio: "Parte es repetición", ok: "Cobertura independiente" }[nivel];
  const sitios = {};
  (d.documentos || []).forEach((x) => { sitios[x.id] = x.sitio; });
  const fuentes = (d.grupos || []).map((g, i) => {
    const copias = g.miembros.filter((m) => m !== g.origen).map((m) => sitios[m] || m);
    return `<li><i style="background:${COLORES[i % COLORES.length]}"></i><div><b>${esc(g.origen_sitio)}</b>
      <small>${copias.length ? `la repiten: ${esc(copias.join(", "))}` : "sin copias"}</small></div></li>`;
  }).join("");
  const pr = d.procedencia;
  const chips = [];
  if (pr) {
    const pl = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;
    if (pr.firmadas_confiables) chips.push(`<span class="chip ok">${pl(pr.firmadas_confiables, "imagen con firma", "imágenes con firma")}</span>`);
    if (pr.generadas_por_ia.length) chips.push(`<span class="chip alerta">${pl(pr.generadas_por_ia.length, "declarada como IA", "declaradas como IA")}</span>`);
    if (pr.firma_rota.length) chips.push(`<span class="chip alerta">${pl(pr.firma_rota.length, "firma rota", "firmas rotas")}</span>`);
    if (pr.fechas_imposibles.length) chips.push(`<span class="chip alerta">${pl(pr.fechas_imposibles.length, "fecha imposible", "fechas imposibles")}</span>`);
    if (!chips.length) chips.push(`<span class="chip">${pl(pr.imagenes, "imagen sin credenciales", "imágenes sin credenciales")}</span>`);
  }
  const informe = d.informe_id ? `${api}/#informe/${d.informe_id}` : null;
  $("#resultado").innerHTML = `
    <section class="tarjeta">
      <div class="medidor">${arco(n ? k / n : 0, color)}
        <div><div class="cifras-grandes">${n} → ${k}<small>página${n === 1 ? "" : "s"} → fuente${k === 1 ? "" : "s"} independiente${k === 1 ? "" : "s"}</small></div>
          <span class="veredicto v-${nivel}">${texto}</span></div></div>
      <p class="resumen">${esc(d.nota_web_real || "")}</p>
      ${d.aviso ? `<div class="aviso">${esc(d.aviso)}</div>` : ""}
    </section>
    ${fuentes ? `<section class="tarjeta"><div class="seccion-cab"><span>De dónde sale</span></div><ul class="fuentes">${fuentes}</ul></section>` : ""}
    ${chips.length ? `<section class="tarjeta"><div class="seccion-cab"><span>Imágenes (C2PA)</span></div><div class="chips">${chips.join("")}</div></section>` : ""}
    <div class="acciones">
      ${informe ? `<a class="grande" style="text-align:center;text-decoration:none" href="${esc(informe)}" target="_blank">Ver informe completo</a>` : "<span></span>"}
      <button class="grande secundario" id="otra-vez">Analizar de nuevo</button>
    </div>`;
  $("#resultado").hidden = false;
  $("#otra-vez").addEventListener("click", () => {
    $("#resultado").hidden = true;
    $("#caja-comparar").hidden = false;
    $("#analizar").disabled = false;
  });
}

async function analizar() {
  const api = await ecoApi();
  const url = PRUEBA || pestanaActual?.url;
  if (!url || !/^https?:/.test(url)) {
    $("#resultado").innerHTML = `<div class="error">ECO solo analiza páginas web (http o https).</div>`;
    $("#resultado").hidden = false;
    return;
  }
  const extra = [...document.querySelectorAll("#lista-pestanas input:checked")].map((c) => c.value);
  $("#analizar").disabled = true;
  $("#caja-comparar").hidden = true;
  $("#resultado").hidden = false;
  $("#resultado").innerHTML = `<section class="tarjeta"><div class="cargando">Leyendo la página${extra.length ? ` y ${extra.length} más` : ""}, extrayendo sus datos y revisando sus imágenes…</div></section>`;
  try {
    const r = await fetch(`${api}/api/analizar_pagina`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, urls_extra: extra, modelo: (await leer("ecoModelo", "")) || null }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || `Error ${r.status}`);
    pintarResultado(d, api);
  } catch (e) {
    $("#resultado").innerHTML = `<div class="error">${esc(e.message.includes("Failed to fetch") ? `No se pudo conectar con el servidor de ECO (${api}).` : e.message)}</div>
      <button class="grande secundario" id="otra-vez" style="margin-top:8px">Intentar de nuevo</button>`;
    $("#otra-vez").addEventListener("click", () => { $("#resultado").hidden = true; $("#caja-comparar").hidden = false; $("#analizar").disabled = false; });
  }
}
$("#analizar").addEventListener("click", analizar);

// ---------------- inicio ----------------
(async () => {
  aplicarTema(await leer("ecoTema", "auto"));
  if (PRUEBA) {
    pestanaActual = { url: PRUEBA, title: PRUEBA };
  } else {
    [pestanaActual] = await chrome.tabs.query({ active: true, currentWindow: true });
  }
  try { $("#sitio").textContent = new URL(pestanaActual.url).hostname.replace(/^www\./, ""); } catch (_) { /* nada */ }
  $("#titulo-pagina").textContent = pestanaActual?.title || "Esta página";
  listarPestanas();
  prepararServidor();
  cargarModelos();
})();
