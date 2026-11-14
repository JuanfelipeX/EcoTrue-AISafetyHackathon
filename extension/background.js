// Menú contextual de ECO: muestra el análisis en un panel flotante dentro de la página.

importScripts("config.js");

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "eco-analizar",
    title: "ECO: ¿cuántas fuentes reales hay detrás de esto?",
    contexts: ["selection", "page"],
  });
});

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
      body: JSON.stringify({ url: tab.url, seleccion: seleccion || null }),
    });
    const datos = await respuesta.json();
    if (!respuesta.ok) {
      await mostrar(tab.id, "error", datos.detail || `Error ${respuesta.status}`);
      return;
    }
    datos.panel_url = datos.mundo ? `${ECO_API}/?mundo=${encodeURIComponent(datos.mundo)}#laboratorio` : null;
    await mostrar(tab.id, "listo", datos);
  } catch (e) {
    await mostrar(tab.id, "error", `No se pudo conectar con el servidor de ECO en ${ECO_API}. ¿Está corriendo?`);
  }
}

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId !== "eco-analizar" || !tab || !tab.id) return;
  analizarEnPestana(tab, info.selectionText);
});
