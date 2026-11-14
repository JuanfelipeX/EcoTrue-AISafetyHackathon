// Dirección del servidor de ECO (uvicorn api.servidor:app --port 8765).
// Si el usuario la fijó en el popup ("Servidor de ECO") se usa esa; si no, se busca un servidor de ECO
// vivo en los puertos habituales y, si no hay ninguno local, se usa el servidor público de ECO en AWS.
const ECO_API_PUBLICA = "https://eco.kibosecondbrain.com";
const ECO_API_DEFECTO = ECO_API_PUBLICA;
const ECO_CANDIDATOS = ["http://localhost:8765", "http://localhost:8766", "http://localhost:8770", "http://localhost:8000",
                        ECO_API_PUBLICA];

async function ecoVivo(base) {
  try {
    const control = new AbortController();
    const reloj = setTimeout(() => control.abort(), 800);
    const r = await fetch(`${base}/api/salud`, { signal: control.signal });
    clearTimeout(reloj);
    return r.ok && (await r.json()).estado === "ok";
  } catch (_) {
    return false;
  }
}

async function ecoApi() {
  let fijado = null;
  try {
    fijado = (await chrome.storage.local.get("ecoApi")).ecoApi || null;
  } catch (_) { /* sin almacenamiento */ }
  if (fijado) return fijado.replace(/\/+$/, "");
  for (const base of ECO_CANDIDATOS) {
    if (await ecoVivo(base)) return base;
  }
  return ECO_API_DEFECTO;
}
