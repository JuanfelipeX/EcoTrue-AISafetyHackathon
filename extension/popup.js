// Popup: analiza la pestaña activa con la API de ECO.

const contenido = document.getElementById("contenido");

function mostrarError(mensaje) {
  contenido.innerHTML = `<div class="eco-error">${ecoEsc(mensaje)}</div>`;
}

async function analizar() {
  // ?url=... permite probar el popup abriéndolo como pestaña; en uso normal se toma la pestaña activa.
  const urlPrueba = new URLSearchParams(location.search).get("url");
  const [pestana] = urlPrueba ? [{ url: urlPrueba }] : await chrome.tabs.query({ active: true, currentWindow: true });
  if (!pestana || !pestana.url) {
    mostrarError("No se pudo leer la dirección de la pestaña.");
    return;
  }
  const ECO_API = await ecoApi();
  contenido.innerHTML = '<div class="eco-cargando">Buscando las páginas relacionadas y comparando sus datos…</div>';
  try {
    const respuesta = await fetch(`${ECO_API}/api/analizar_pagina`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: pestana.url }),
    });
    const datos = await respuesta.json();
    if (!respuesta.ok) {
      mostrarError(datos.detail || `Error ${respuesta.status}`);
      return;
    }
    datos.panel_url = `${ECO_API}/?mundo=${encodeURIComponent(datos.mundo || "")}#laboratorio`;
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
