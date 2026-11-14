// Dirección del servidor de ECO (uvicorn api.servidor:app --port 8765).
// Se puede cambiar desde el popup ("Servidor de ECO"); el valor queda en chrome.storage.
const ECO_API_DEFECTO = "http://localhost:8765";

async function ecoApi() {
  try {
    const r = await chrome.storage.local.get("ecoApi");
    return (r.ecoApi || ECO_API_DEFECTO).replace(/\/+$/, "");
  } catch (_) {
    return ECO_API_DEFECTO;
  }
}
