// Servidor de ECO. Por defecto, el público (https://eco.kibosecondbrain.com). Solo se usa otro si la persona lo
// fija en Ajustes → «Servidor de ECO» (por ejemplo, uno local para desarrollo). Si el fijado no responde, se vuelve
// al público para que la extensión nunca quede inservible.
const ECO_API_PUBLICA = "https://eco.kibosecondbrain.com";
const ECO_API_DEFECTO = ECO_API_PUBLICA;

async function ecoVivo(base) {
  try {
    const control = new AbortController();
    const reloj = setTimeout(() => control.abort(), 1500);
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
  if (fijado) {
    fijado = fijado.replace(/\/+$/, "");
    if (fijado === ECO_API_PUBLICA || await ecoVivo(fijado)) return fijado;
  }
  return ECO_API_PUBLICA;
}
