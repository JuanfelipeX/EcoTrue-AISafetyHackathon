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
  $("#servidor-publico").addEventListener("click", async () => {
    try { await chrome.storage.local.remove("ecoApi"); } catch (_) { /* nada */ }
    $("#servidor").value = ECO_API_PUBLICA;
    $("#estado-servidor").textContent = "Listo: se usa el servidor público.";
    cargarModelos();
  });
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

function fraseConclusion(d) {
  const n = d.fuentes_aparentes, k = d.fuentes_efectivas, origen = (d.grupos || [])[0]?.origen_sitio || "un mismo medio";
  if (n <= 1) return "Solo hay una página: no se puede saber si otras fuentes lo confirman.";
  if (k === 1) return `Todo sale de ${origen}: que muchas webs lo repitan no lo hace más confiable.`;
  if (k < n) return `${k} medios informan por su cuenta; ${n - k} solo repiten. Apóyate en los ${k}.`;
  return `${k} medios lo informan por su cuenta: hay cobertura independiente.`;
}

function pintarResultado(d, api) {
  if (d.sin_cobertura) {
    $("#final").innerHTML = `<section class="tarjeta"><div class="mini-conclusion alerta"><b>⚪ Ningún medio lo reporta</b>
      ${esc(d.nota_web_real || "")} No lo reenvíes hasta que un medio o una fuente oficial lo confirme.</div></section>
      <button class="grande secundario" id="otra-vez">Analizar de nuevo</button>`;
    $("#resultado").hidden = false;
    $("#otra-vez").addEventListener("click", () => { $("#resultado").hidden = true; $("#caja-tema").hidden = false; $("#analizar").disabled = false; });
    return;
  }
  const n = d.fuentes_aparentes, k = d.fuentes_efectivas;
  const nivel = n <= 1 ? "medio" : k <= 1 ? "alerta" : k < n ? "medio" : "ok";
  const color = { alerta: "var(--mal)", medio: "var(--medio)", ok: "var(--bien)" }[nivel];
  const texto = n <= 1 ? "Solo una página" : { alerta: "Un solo origen", medio: "Parte es repetición", ok: "Cobertura independiente" }[nivel];
  const sitios = {};
  (d.documentos || []).forEach((x) => { sitios[x.id] = x.sitio; });
  const f = d.fuentes;
  const propias = f ? f.con_reporteria_propia.slice(0, 6).map((x, i) => `<li><i style="background:${COLORES[i % COLORES.length]}"></i><div>
      <a href="${esc(x.url || "#")}" target="_blank"><b>${esc(x.sitio)}</b></a>
      <small>${x.datos_propios} dato${x.datos_propios === 1 ? "" : "s"} propio${x.datos_propios === 1 ? "" : "s"}${x.lo_repiten.length ? ` · la repiten: ${esc(x.lo_repiten.join(", "))}` : ""}</small></div></li>`).join("") : "";
  const fuentes = propias ? "" : (d.grupos || []).map((g, i) => {
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
  $("#final").innerHTML = `
    <section class="tarjeta">
      <div class="medidor">${arco(n ? k / n : 0, color)}
        <div><div class="cifras-grandes">${n} → ${k}<small>página${n === 1 ? "" : "s"} → fuente${k === 1 ? "" : "s"} independiente${k === 1 ? "" : "s"}</small></div>
          <span class="veredicto v-${nivel}">${texto}</span></div></div>
      <p class="resumen"><b>${esc(fraseConclusion(d))}</b></p>
      <p class="resumen">${esc(d.nota_web_real || "")}</p>
      ${d.aviso ? `<div class="aviso">${esc(d.aviso)}</div>` : ""}
      ${d.aviso_buscador ? `<div class="aviso">${esc(d.aviso_buscador)}</div>` : ""}
    </section>
    ${propias ? `<section class="tarjeta"><div class="seccion-cab"><span>Con reportería propia</span><small>ordenadas por datos propios</small></div><ul class="fuentes">${propias}</ul>
      ${f.solo_repiten.length ? `<p class="pista">${f.solo_repiten.length} nota${f.solo_repiten.length === 1 ? "" : "s"} solo repite${f.solo_repiten.length === 1 ? "" : "n"} a otras.</p>` : ""}</section>` : ""}
    <section class="tarjeta"><div class="seccion-cab"><span>Grafo de procedencia</span></div><div id="grafo"></div></section>
    ${fuentes ? `<section class="tarjeta"><div class="seccion-cab"><span>De dónde sale</span></div><ul class="fuentes">${fuentes}</ul></section>` : ""}
    ${(d.corroborados || []).length ? `<section class="tarjeta"><div class="seccion-cab"><span>Corroborado por 2+ fuentes</span></div><ul class="fuentes">${d.corroborados.slice(0, 4).map((t) => `<li><i style="background:var(--bien)"></i><div>${esc(t)}</div></li>`).join("")}</ul></section>` : ""}
    ${chips.length ? `<section class="tarjeta"><div class="seccion-cab"><span>Imágenes (C2PA)</span></div><div class="chips">${chips.join("")}</div></section>` : ""}
    <div class="acciones">
      ${informe ? `<a class="grande" style="text-align:center;text-decoration:none" href="${esc(informe)}" target="_blank">Ver informe completo</a>` : "<span></span>"}
      <button class="grande secundario" id="otra-vez">Analizar de nuevo</button>
    </div>`;
  ecoGrafo($("#grafo"), d);
  $("#resultado").hidden = false;
  $("#otra-vez").addEventListener("click", () => {
    $("#resultado").hidden = true;
    $("#caja-tema").hidden = false;
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
  await ejecutar(api, { modo: "pagina", url, modelo: (await leer("ecoModelo", "")) || null }, "El agente está analizando esta noticia");
}

async function investigar() {
  const api = await ecoApi();
  const tema = $("#tema").value.trim();
  if (tema.length < 4) { $("#tema").focus(); return; }
  await ejecutar(api, { modo: "tema", tema, modelo: (await leer("ecoModelo", "")) || null }, `Investigando «${tema}»`);
}
$("#investigar").addEventListener("click", investigar);
$("#tema").addEventListener("keydown", (e) => { if (e.key === "Enter") investigar(); });

async function ejecutar(api, cuerpo, titulo) {
  $("#analizar").disabled = true;
  $("#caja-tema").hidden = true;
  $("#resultado").hidden = false;
  $("#resultado").innerHTML = `<div id="bitacora"></div><div id="final"></div>`;
  const bit = ecoBitacora($("#bitacora"), titulo);
  const reintentar = () => { $("#resultado").hidden = true; $("#caja-tema").hidden = false; $("#analizar").disabled = false; };
  await ecoAgente(api, cuerpo, {
    alEvento: (e) => bit.evento(e),
    alError: (e) => {
      bit.terminar(false, e.message.includes("Failed to fetch") ? `No se pudo conectar con el servidor de ECO (${api}).` : e.message);
      $("#final").innerHTML = `<button class="grande secundario" id="otra-vez">Intentar de nuevo</button>`;
      $("#otra-vez").addEventListener("click", reintentar);
    },
    alFin: (d) => {
      bit.terminar(true, `Listo: ${d.fuentes_aparentes} → ${d.fuentes_efectivas}`);
      $("#bitacora .ag-pasos").style.maxHeight = "150px";
      pintarResultado(d, api);
    },
  });
}

$("#analizar").addEventListener("click", analizar);

// ---------------- modos: página, nota de voz y captura ----------------
document.querySelectorAll("#modos button").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll("#modos button").forEach((x) => x.classList.toggle("activo", x === b));
  const m = b.dataset.modo;
  $("#caja-pagina").hidden = m !== "pagina";
  $("#caja-tema").hidden = m !== "pagina";
  $("#caja-voz").hidden = m !== "voz";
  $("#caja-captura").hidden = m !== "captura";
  $("#resultado").hidden = true;
  $("#resultado").innerHTML = "";
}));

function miniConclusion(nivel, titulo, texto) {
  return `<div class="mini-conclusion ${nivel}"><b>${esc(titulo)}</b>${esc(texto || "")}</div>`;
}

function conclusionVoz(v) {
  const d = (v && v.detector) || {};
  const e = d.error_de_referencia?.opus_16k;
  const fiab = e != null ? ` Se equivoca en ~${Math.round(e * 100)} de cada 100 notas de voz.` : "";
  if (d.veredicto === "sintetica") return miniConclusion("alerta", "🔴 Probablemente voz sintética", "Confirma por otro canal antes de creerle." + fiab);
  if (d.veredicto === "real") return miniConclusion("ok", "🟢 Probablemente voz real", "Si piden dinero o datos, confirma igual por otro canal." + fiab);
  if (d.veredicto === "incierto") return miniConclusion("medio", "🟡 Voz: no concluyente", "Confirma por otro canal." + fiab);
  return miniConclusion("medio", "⚪ Voz: sin veredicto", "El detector no es fiable con este audio.");
}

function conclusionArchivo(a) {
  if (!a) return "";
  if (a.estado === "rota") return miniConclusion("alerta", "🔴 Imagen alterada después de firmarse", "");
  if (a.ia === "declarada") return miniConclusion("alerta", "🤖 Imagen hecha o modificada con IA", "Lo declara el propio archivo.");
  if (a.estado === "confiable") return miniConclusion("ok", "✅ Imagen con origen verificado", `Firmada por ${a.firmante}.`);
  if (a.ia === "indicio" || (a.forense?.rasgos_atipicos ?? 0) >= 2) return miniConclusion("medio", "🟡 La imagen tiene rasgos poco comunes", "Búscala con una búsqueda inversa.");
  return miniConclusion("ok", "🟢 Imagen sin señales de IA ni de manipulación", "Sin firma digital: no se puede certificar quién la hizo.");
}

async function enviarMultimodal(ruta, blob, nombre, titulo, pintarExtra) {
  const api = await ecoApi();
  $("#resultado").hidden = false;
  $("#resultado").innerHTML = `<section class="tarjeta"><div class="cargando">${esc(ruta.includes("voz") ? "Escuchando y transcribiendo…" : "Leyendo el texto de la imagen…")}</div></section>`;
  try {
    const r = await fetch(`${api}${ruta}?nombre=${encodeURIComponent(nombre)}`, { method: "POST", body: blob });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || `Error ${r.status}`);
    const texto = d.transcripcion ?? d.texto;
    const alertas = (d.alertas || []).map((a) => `<li>⚠ ${esc(a)}</li>`).join("");
    $("#resultado").innerHTML = `<section class="tarjeta">
      <div class="seccion-cab"><span>${esc(titulo)}</span></div>
      <div class="lectura-texto">${esc(texto || "(sin texto)")}</div>
      ${alertas ? `<ul class="alertas">${alertas}</ul>` : ""}
      ${d.tipo === "sin_afirmacion" ? `<p class="pista">No hay una afirmación verificable.</p>` : `
        <div class="seccion-cab" style="margin-top:6px"><span>Lo que afirma</span><small>puedes corregirlo</small></div>
        <textarea id="afirmacion-extraida" rows="2">${esc(d.afirmacion || "")}</textarea>
        <button class="grande" id="verificar-extraida">Verificar qué fuentes lo respaldan</button>`}
      ${pintarExtra(d)}
    </section>`;
    $("#verificar-extraida")?.addEventListener("click", async () => {
      const tema = $("#afirmacion-extraida").value.trim();
      if (tema.length < 4) return;
      await ejecutar(api, { modo: "tema", tema, modelo: (await leer("ecoModelo", "")) || null }, `Verificando «${tema.slice(0, 60)}»`);
    });
  } catch (e) {
    $("#resultado").innerHTML = `<div class="error">${esc(e.message)}</div>`;
  }
}

$("#enviar-nota").addEventListener("click", () => {
  const f = $("#archivo-nota").files[0];
  if (!f) { $("#archivo-nota").click(); return; }
  enviarMultimodal("/api/nota_de_voz", f, f.name, "Lo que dice la nota de voz", (d) => conclusionVoz(d.voz));
});
$("#archivo-captura").addEventListener("change", () => {
  const f = $("#archivo-captura").files[0];
  if (f) enviarMultimodal("/api/leer_captura", f, f.name, "Lo que dice la captura", (d) => conclusionArchivo(d.archivo));
});
$("#capturar-pestana").addEventListener("click", async () => {
  try {
    const url = await chrome.tabs.captureVisibleTab(undefined, { format: "png" });
    const blob = await (await fetch(url)).blob();
    enviarMultimodal("/api/leer_captura", blob, "pestana.png", "Lo que dice la pestaña capturada", (d) => conclusionArchivo(d.archivo));
  } catch (e) {
    $("#resultado").hidden = false;
    $("#resultado").innerHTML = `<div class="error">No se pudo capturar esta pestaña (${esc(e.message)}). Sube una imagen.</div>`;
  }
});
$("#limpiar").addEventListener("click", () => {
  $("#resultado").innerHTML = "";
  $("#resultado").hidden = true;
  $("#caja-tema").hidden = false;
  $("#tema").value = "";
  $("#analizar").disabled = false;
  mostrarVista("principal");
});

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
  prepararServidor();
  cargarModelos();
})();
