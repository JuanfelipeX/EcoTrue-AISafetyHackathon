// Interfaz bilingüe (español / inglés) sin tocar el HTML: se traduce cada texto visible con un diccionario
// (web/i18n/en.json). Los números se tratan como comodines (#), así "5 páginas → 1 fuente" y "7 páginas → 3 fuentes"
// usan la misma entrada. Un MutationObserver traduce también lo que la página dibuja después (resultados, informes).
(function () {
  const ATRIBUTOS = ["placeholder", "title", "aria-label", "alt"];
  const OMITIR = new Set(["SCRIPT", "STYLE", "CODE", "PRE", "TEXTAREA", "INPUT"]);
  let idioma = "es";
  let dic = null;
  let observador = null;
  const originales = new WeakMap(); // nodo de texto → texto en español
  const attrOriginales = new WeakMap(); // elemento → {atributo: texto}

  const plantilla = (t) => t.replace(/\d+(?:[.,]\d+)*/g, "#");
  const numeros = (t) => t.match(/\d+(?:[.,]\d+)*/g) || [];

  function traducirTexto(texto) {
    const limpio = texto.trim().replace(/\s+/g, " ");
    if (!limpio || !/[a-záéíóúñ]/i.test(limpio)) return null;
    let en = dic[limpio];
    if (en === undefined) {
      const clave = plantilla(limpio);
      en = dic[clave];
      if (en === undefined) return null;
      const ns = numeros(limpio);
      let i = 0;
      en = en.replace(/#/g, () => (i < ns.length ? ns[i++] : "#"));
    }
    const inicio = texto.match(/^\s*/)[0], fin = texto.match(/\s*$/)[0];
    return inicio + en + fin;
  }

  function enDOM(raiz, haciaIngles) {
    const recorrido = document.createTreeWalker(raiz, NodeFilter.SHOW_TEXT, {
      acceptNode: (n) => (n.parentElement && !OMITIR.has(n.parentElement.tagName) && !n.parentElement.closest("[data-sin-traducir]")
        ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT),
    });
    const nodos = [];
    while (recorrido.nextNode()) nodos.push(recorrido.currentNode);
    for (const n of nodos) {
      if (haciaIngles) {
        const original = originales.has(n) ? originales.get(n) : n.nodeValue;
        const t = traducirTexto(original);
        if (t !== null && t !== n.nodeValue) {
          originales.set(n, original);
          n.nodeValue = t;
        }
      } else if (originales.has(n)) {
        n.nodeValue = originales.get(n);
        originales.delete(n);
      }
    }
    const elementos = raiz.nodeType === 1 ? [raiz, ...raiz.querySelectorAll("*")] : [];
    for (const el of elementos) {
      for (const a of ATRIBUTOS) {
        if (!el.hasAttribute(a)) continue;
        const guardados = attrOriginales.get(el) || {};
        if (haciaIngles) {
          const original = guardados[a] ?? el.getAttribute(a);
          const t = traducirTexto(original);
          if (t !== null) { guardados[a] = original; attrOriginales.set(el, guardados); el.setAttribute(a, t.trim()); }
        } else if (guardados[a] !== undefined) {
          el.setAttribute(a, guardados[a]);
        }
      }
    }
  }

  async function cargar() {
    if (dic) return dic;
    try {
      const r = await fetch("/web/i18n/en.json", { cache: "no-cache" });
      dic = await r.json();
    } catch (_) { dic = {}; }
    return dic;
  }

  async function cambiar(nuevo) {
    idioma = nuevo;
    try { localStorage.setItem("eco-idioma", nuevo); } catch (_) { /* nada */ }
    document.documentElement.lang = nuevo;
    const boton = document.getElementById("idioma");
    if (boton) { boton.textContent = nuevo === "en" ? "ES" : "EN"; boton.title = nuevo === "en" ? "Ver en español" : "View in English"; }
    if (nuevo === "en") {
      await cargar();
      enDOM(document.body, true);
      if (!observador) {
        observador = new MutationObserver((cambios) => {
          if (idioma !== "en") return;
          for (const c of cambios) {
            if (c.type === "characterData") { if (!originales.has(c.target)) enDOM(c.target.parentElement || document.body, true); continue; }
            c.addedNodes.forEach((n) => { if (n.nodeType === 1) enDOM(n, true); else if (n.nodeType === 3 && n.parentElement) enDOM(n.parentElement, true); });
          }
        });
      }
      observador.observe(document.body, { childList: true, subtree: true, characterData: true });
    } else {
      if (observador) observador.disconnect();
      enDOM(document.body, false);
    }
  }

  window.ecoIdioma = () => idioma;
  window.ecoT = (texto) => (idioma === "en" && dic ? (traducirTexto(texto) ?? texto) : texto);
  document.addEventListener("DOMContentLoaded", () => {
    const boton = document.getElementById("idioma");
    if (boton) boton.addEventListener("click", () => cambiar(idioma === "en" ? "es" : "en"));
    let guardado = null;
    try { guardado = localStorage.getItem("eco-idioma"); } catch (_) { /* nada */ }
    const inicial = new URLSearchParams(location.search).get("lang") || guardado ||
      ((navigator.language || "es").startsWith("es") ? "es" : "en");
    if (inicial === "en") cambiar("en");
  });
})();
