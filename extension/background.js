// Menú contextual de ECO: muestra el análisis en un panel flotante dentro de la página.

importScripts("config.js");

// El menú se recrea al instalar y cada vez que arranca el navegador (clic derecho; el clic izquierdo no abre menús).
function crearMenus() {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({ id: "eco-analizar", title: "ECO: ¿cuántas fuentes reales hay detrás de esta noticia?", contexts: ["page"] });
    chrome.contextMenus.create({ id: "eco-seleccion", title: "ECO: ¿cuántas fuentes respaldan «%s»?", contexts: ["selection"] });
    chrome.contextMenus.create({ id: "eco-archivo", title: "ECO: ¿de dónde viene esta imagen? ¿La hizo una IA?", contexts: ["image", "video"] });
  });
}
chrome.runtime.onInstalled.addListener(crearMenus);
chrome.runtime.onStartup.addListener(crearMenus);

// Se ejecuta dentro de la página: crea o actualiza el panel.
function pintarPanel(estado, datos) {
  let panel = document.getElementById("eco-panel");
  if (!panel) {
    panel = document.createElement("div");
    panel.id = "eco-panel";
    panel.className = "eco-raiz";
    document.body.appendChild(panel);
  }
  const cabecera = '<div class="eco-cabecera"><h1>ECO</h1>' +
    '<button class="eco-cerrar" title="Cerrar">×</button></div>';
  let cuerpo;
  if (estado === "cargando") {
    cuerpo = '<div class="eco-cargando">Leyendo la página y sus fuentes, y comparando sus datos…</div>';
  } else if (estado === "cargando-archivo") {
    cuerpo = '<div class="eco-cargando">Verificando la firma C2PA y las marcas de IA del archivo…</div>';
  } else if (estado === "archivo") {
    cuerpo = globalThis.ecoRenderArchivo(datos);
  } else if (estado === "error") {
    cuerpo = `<div class="eco-error">${globalThis.ecoEsc(datos)}</div>`;
  } else {
    cuerpo = globalThis.ecoRender(datos);
  }
  panel.innerHTML = cabecera + cuerpo;
  panel.querySelector(".eco-cerrar").addEventListener("click", () => panel.remove());
}

async function mostrar(tabId, estado, datos) {
  await chrome.scripting.executeScript({ target: { tabId }, func: pintarPanel, args: [estado, datos] });
}

async function analizarEnPestana(tab, seleccion) {
  try {
    await chrome.scripting.insertCSS({ target: { tabId: tab.id }, files: ["estilos.css"] });
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["render.js"] });
    await mostrar(tab.id, "cargando", null);
  } catch (e) {
    console.error("ECO: no se pudo dibujar en esta página", e);
    return;
  }
  const ECO_API = await ecoApi();
  try {
    const respuesta = await fetch(`${ECO_API}/api/analizar_pagina`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: tab.url, seleccion: seleccion || null,
        modelo: ((await chrome.storage.local.get("ecoModelo")).ecoModelo) || null }),
    });
    const datos = await respuesta.json();
    if (!respuesta.ok) {
      await mostrar(tab.id, "error", datos.detail || `Error ${respuesta.status}`);
      return;
    }
    datos.panel_url = datos.informe_id ? `${ECO_API}/#informe/${datos.informe_id}` : null;
    await mostrar(tab.id, "listo", datos);
  } catch (e) {
    await mostrar(tab.id, "error", `No se pudo conectar con el servidor de ECO en ${ECO_API}. ¿Está corriendo?`);
  }
}

async function verificarArchivoEnPestana(tab, url) {
  try {
    await chrome.scripting.insertCSS({ target: { tabId: tab.id }, files: ["estilos.css"] });
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["render.js"] });
  } catch (e) {
    console.error("ECO: no se pudo dibujar en esta página", e);
    return;
  }
  if (!url || !/^https?:/.test(url)) {
    await mostrar(tab.id, "error", "Esta imagen está incrustada en la página (no tiene dirección propia). Descárgala y súbela en el panel de ECO → Analizar.");
    return;
  }
  await mostrar(tab.id, "cargando-archivo", null);
  const ECO_API = await ecoApi();
  try {
    const respuesta = await fetch(`${ECO_API}/api/verificar_imagen`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url }),
    });
    const datos = await respuesta.json();
    if (!respuesta.ok) {
      await mostrar(tab.id, "error", datos.detail || `Error ${respuesta.status}`);
      return;
    }
    await mostrar(tab.id, "archivo", datos);
  } catch (e) {
    await mostrar(tab.id, "error", `No se pudo conectar con el servidor de ECO en ${ECO_API}.`);
  }
}

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (!tab || !tab.id) return;
  if (info.menuItemId === "eco-archivo") verificarArchivoEnPestana(tab, info.srcUrl);
  else if (info.menuItemId === "eco-seleccion") analizarEnPestana(tab, info.selectionText);
  else if (info.menuItemId === "eco-analizar") analizarEnPestana(tab, null);
});
