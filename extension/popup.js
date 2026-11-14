// Popup: analiza la pestaña activa con la API de ECO.

const contenido = document.getElementById("contenido");

function mostrarError(mensaje) {
  contenido.innerHTML = `<div class="eco-error">${ecoEsc(mensaje)}</div>`;
}

const PALABRAS_VACIAS = new Set("de la el los las un una y o en por para con del al que se su sus es son a lo como más tras sobre".split(" "));
function palabras(t) {
  return new Set((t || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").split(/[^a-z0-9ñ]+/)
    .filter((w) => w.length > 3 && !PALABRAS_VACIAS.has(w)));
}

async function listarPestanas() {
  if (new URLSearchParams(location.search).get("url")) return;
  const [activa] = await chrome.tabs.query({ active: true, currentWindow: true });
  const todas = await chrome.tabs.query({ currentWindow: true });
  const otras = todas.filter((t) => t.id !== activa?.id && /^https?:/.test(t.url || ""));
  if (!otras.length) return;
  const base = palabras(activa?.title);
  document.getElementById("pestanas").innerHTML = otras.slice(0, 12).map((t) => {
    const comunes = [...palabras(t.title)].filter((w) => base.has(w)).length;
    return `<label><input type="checkbox" value="${ecoEsc(t.url)}" ${comunes >= 2 ? "checked" : ""}>
      <span>${ecoEsc(t.title || t.url)}<small>${ecoEsc(new URL(t.url).hostname)}</small></span></label>`;
  }).join("");
  document.getElementById("pestanas-caja").hidden = false;
}
listarPestanas();

async function analizar() {
  // ?url=... permite probar el popup abriéndolo como pestaña; en uso normal se toma la pestaña activa.
  const urlPrueba = new URLSearchParams(location.search).get("url");
  const [pestana] = urlPrueba ? [{ url: urlPrueba }] : await chrome.tabs.query({ active: true, currentWindow: true });
  if (!pestana || !pestana.url) {
    mostrarError("No se pudo leer la dirección de la pestaña.");
    return;
  }
  const ECO_API = await ecoApi();
  const caja = document.getElementById("pestanas-caja");
  if (caja) caja.hidden = true;
  contenido.innerHTML = '<div class="eco-cargando">Leyendo la página y sus fuentes, y comparando sus datos… (puede tardar unos segundos)</div>';
  try {
    const respuesta = await fetch(`${ECO_API}/api/analizar_pagina`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: pestana.url,
        urls_extra: [...document.querySelectorAll("#pestanas input:checked")].map((c) => c.value),
      }),
    });
    const datos = await respuesta.json();
    if (!respuesta.ok) {
      mostrarError(datos.detail || `Error ${respuesta.status}`);
      return;
    }
    datos.panel_url = datos.mundo ? `${ECO_API}/?mundo=${encodeURIComponent(datos.mundo)}#laboratorio` : null;
    contenido.innerHTML = ecoRender(datos);
  } catch (e) {
    mostrarError(`No se pudo conectar con el servidor de ECO en ${ECO_API}. ¿Está corriendo? (${e.message})`);
  }
}

document.getElementById("analizar").addEventListener("click", analizar);

// Ajuste del servidor
const campoServidor = document.getElementById("servidor");
ecoApi().then((u) => { campoServidor.value = u; });
document.getElementById("guardar-servidor").addEventListener("click", async () => {
  const valor = campoServidor.value.trim() || ECO_API_DEFECTO;
  await chrome.storage.local.set({ ecoApi: valor });
  document.getElementById("estado-servidor").textContent = "Guardado.";
});
