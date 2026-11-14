// Componentes compartidos por el panel web y la extensión:
//   ecoAgente(): llama a /api/agente y entrega cada paso real del análisis a medida que ocurre.
//   ecoBitacora(): dibuja esos pasos como la bitácora en vivo del agente.
//   ecoGrafo(): grafo de procedencia interactivo (nodos = publicaciones, líneas = quién deriva de quién).
(function () {
  const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const hora = (iso) => { if (!iso) return ""; const d = new Date(iso); return isNaN(d) ? "" : d.toLocaleString([], { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }); };

  async function ecoAgente(base, cuerpo, { alEvento, alFin, alError }) {
    try {
      const r = await fetch(`${base}/api/agente`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo) });
      if (!r.ok || !r.body) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || `Error ${r.status}`);
      }
      const lector = r.body.getReader();
      const dec = new TextDecoder();
      let resto = "";
      for (;;) {
        const { value, done } = await lector.read();
        if (done) break;
        resto += dec.decode(value, { stream: true });
        let corte;
        while ((corte = resto.indexOf("\n\n")) >= 0) {
          const bloque = resto.slice(0, corte);
          resto = resto.slice(corte + 2);
          const linea = bloque.split("\n").find((l) => l.startsWith("data: "));
          if (!linea) continue;
          const ev = JSON.parse(linea.slice(6));
          if (ev.etapa === "fin") alFin(ev.resultado);
          else if (ev.etapa === "error") alError(new Error(ev.texto));
          else alEvento(ev);
        }
      }
    } catch (e) {
      alError(e);
    }
  }

  // ---------------- bitácora en vivo ----------------
  function ecoBitacora(contenedor, titulo) {
    contenedor.innerHTML = `<div class="ag-bitacora"><div class="ag-cab"><span class="ag-pulso"></span><b>${esc(titulo || "El agente está trabajando")}</b>
      <span class="ag-reloj">0 s</span></div><ol class="ag-pasos"></ol></div>`;
    const lista = contenedor.querySelector(".ag-pasos");
    const reloj = contenedor.querySelector(".ag-reloj");
    const inicio = Date.now();
    const tic = setInterval(() => { reloj.textContent = `${Math.round((Date.now() - inicio) / 1000)} s`; }, 500);
    let pasoLLM = null, ticLLM = null;
    const agregar = (icono, clase, html) => {
      const li = document.createElement("li");
      li.className = `ag-paso ${clase || ""}`;
      li.innerHTML = `<span class="ag-icono">${icono}</span><div>${html}</div>`;
      lista.appendChild(li);
      lista.scrollTop = lista.scrollHeight;
      return li;
    };
    const cerrarLLM = () => { if (ticLLM) { clearInterval(ticLLM); ticLLM = null; } if (pasoLLM) pasoLLM.classList.remove("activo"); };
    let decisiones = 0;
    return {
      evento(e) {
        switch (e.etapa) {
          case "buscar": agregar("🔎", "", `Buscando cobertura de <b>«${esc(e.consulta)}»</b>${e.dias ? ` (últimos ${e.dias} días)` : ""}`); break;
          case "encontrada": agregar("📰", "sub", `<b>${esc(e.sitio)}</b> <span class="ag-tenue">${esc(hora(e.fecha))}</span><div class="ag-tenue">${esc((e.titulo || "").slice(0, 110))}</div>`); break;
          case "leer": agregar("📖", "sub", `${esc(e.texto || "Leyendo")} <span class="ag-tenue">${esc((e.url || "").replace(/^https?:\/\//, "").slice(0, 60))}</span>`); break;
          case "leida": agregar("✓", "sub ok", `<b>${esc(e.sitio)}</b>: ${e.parrafos} párrafos, ${e.imagenes} imágenes`); break;
          case "llm":
            pasoLLM = agregar("🧠", "activo", `<b>${esc(e.modelo)}</b> está leyendo ${e.paginas} páginas (${e.palabras} palabras) y extrayendo los datos verificables <span class="ag-tenue ag-llm">0 s</span>`);
            { const t0 = Date.now(), etq = pasoLLM.querySelector(".ag-llm"); ticLLM = setInterval(() => { etq.textContent = `${Math.round((Date.now() - t0) / 1000)} s`; }, 500); }
            break;
          case "hechos": cerrarLLM(); agregar("🧩", e.aviso ? "alerta" : "ok", e.aviso ? esc(e.aviso) : `<b>${e.n} datos</b> extraídos y alineados entre páginas (las paráfrasis cuentan como un solo dato)`); break;
          case "regla": agregar("⚖️", "", `Regla de independencia, en orden cronológico: <b>${e.paginas} páginas → ${e.independientes} fuentes independientes</b>`); break;
          case "decision": {
            decisiones += 1;
            const li = agregar(e.independiente ? "●" : "↳", `sub ${e.independiente ? "propia" : "copia"}`,
              e.independiente ? `<b>${esc(e.sitio)}</b> aporta ${e.nuevos} dato${e.nuevos === 1 ? "" : "s"} nuevo${e.nuevos === 1 ? "" : "s"} → fuente propia`
                : `<b>${esc(e.sitio)}</b> repite a <b>${esc(e.deriva_de || "una página anterior")}</b> <span class="ag-tenue">(${esc(e.motivo || "")})</span>`);
            li.style.animationDelay = `${Math.min(decisiones, 12) * 70}ms`;
            break;
          }
          case "imagenes": agregar("🖼️", "", `Imágenes: ${e.imagenes} revisadas · ${e.confiables} con firma C2PA${e.ia ? ` · ${e.ia} declaradas IA` : ""}${e.rotas ? ` · ${e.rotas} firmas rotas` : ""}${e.fechas ? ` · ${e.fechas} fechas imposibles` : ""}`); break;
          case "aviso": agregar("⚠", "alerta", esc(e.texto)); break;
          default: break;
        }
      },
      terminar(ok, texto) {
        cerrarLLM();
        clearInterval(tic);
        contenedor.querySelector(".ag-pulso")?.classList.add(ok ? "listo" : "fallo");
        contenedor.querySelector(".ag-cab b").textContent = texto || (ok ? "Análisis terminado" : "No se pudo completar");
      },
    };
  }

  // ---------------- grafo de procedencia ----------------
  const COLORES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];

  function clasificar(p) {
    if (p.independiente) return { tipo: "propia", etiqueta: "Fuente propia" };
    if ((p.motivo || "").includes("casi idéntico")) return { tipo: "literal", etiqueta: "Copia casi literal" };
    if ((p.motivo || "").startsWith("usa la foto")) return { tipo: "foto", etiqueta: "Depende de otro medio (foto firmada)" };
    return { tipo: "repite", etiqueta: "Repite sin datos propios" };
  }

  function ecoGrafo(contenedor, res) {
    const paginas = res.paginas || [];
    const docs = Object.fromEntries((res.documentos || []).map((d) => [d.id, d]));
    if (!paginas.length) { contenedor.innerHTML = ""; return; }
    const grupos = res.grupos || [];
    const grupoDe = {};
    grupos.forEach((g, i) => g.miembros.forEach((m) => { grupoDe[m] = i; }));
    // Disposición: columnas por fuente independiente, filas por orden cronológico dentro de cada columna.
    const ancho = Math.max(320, Math.min(860, contenedor.clientWidth || 360));
    const cols = Math.max(1, grupos.length);
    const paso = ancho / cols;
    const filaDe = {}, pos = {};
    paginas.forEach((p) => { const g = grupoDe[p.id] ?? 0; filaDe[g] = (filaDe[g] ?? -1) + 1; pos[p.id] = { x: paso * g + paso / 2, y: 46 + filaDe[g] * 78 }; });
    const alto = Math.max(...Object.values(pos).map((q) => q.y)) + 52;
    const aristas = paginas.filter((p) => p.deriva_de && pos[p.deriva_de]).map((p) => {
      const a = pos[p.deriva_de], b = pos[p.id], c = COLORES[(grupoDe[p.id] ?? 0) % COLORES.length];
      const medio = (a.y + b.y) / 2;
      return `<path class="gr-arista" d="M${a.x} ${a.y + 47} C${a.x} ${medio + 16} ${b.x} ${medio + 16} ${b.x} ${b.y - 17}" stroke="${c}"/>`;
    }).join("");
    const nodos = paginas.map((p) => {
      const { x, y } = pos[p.id];
      const c = COLORES[(grupoDe[p.id] ?? 0) % COLORES.length];
      const k = clasificar(p);
      const sitio = (p.sitio || p.id).replace(/^www\./, "");
      const actual = res.pagina_actual && docs[p.id]?.url === res.pagina_actual;
      return `<g class="gr-nodo ${k.tipo}${actual ? " actual" : ""}" data-id="${esc(p.id)}" transform="translate(${x},${y})" tabindex="0">
        ${k.tipo === "propia" ? `<circle r="21" class="gr-halo" stroke="${c}"/>` : ""}
        <circle r="15" class="gr-disco" stroke="${c}"/>
        <circle r="${k.tipo === "propia" ? 6.5 : 4.5}" fill="${k.tipo === "propia" ? c : "none"}" stroke="${c}" stroke-width="2"/>
        <text y="31" class="gr-nombre">${esc(sitio.length > 18 ? sitio.slice(0, 17) + "…" : sitio)}</text>
        <text y="42" class="gr-hora">${esc(hora(p.fecha))}${actual ? " · actual" : ""}</text></g>`;
    }).join("");
    contenedor.innerHTML = `<div class="gr-leyenda"><span><i class="propia"></i>Fuente propia</span><span><i class="repite"></i>Repite</span><span><i class="literal"></i>Copia casi literal</span>
        <span class="gr-pista">Toca un nodo para ver por qué</span></div>
      <svg class="gr-lienzo" viewBox="0 0 ${ancho} ${alto}" role="img" aria-label="Grafo de procedencia">${aristas}${nodos}</svg>
      <div class="gr-ficha"></div>`;
    const ficha = contenedor.querySelector(".gr-ficha");
    const mostrar = (id) => {
      const p = paginas.find((x) => x.id === id);
      if (!p) return;
      const d = docs[id] || {};
      const k = clasificar(p);
      const madre = p.deriva_de ? (docs[p.deriva_de]?.sitio || p.deriva_de) : null;
      contenedor.querySelectorAll(".gr-nodo").forEach((n) => n.classList.toggle("sel", n.dataset.id === id));
      ficha.innerHTML = `<div class="gr-ficha-cab"><b>${esc(p.sitio)}</b><span class="gr-etq ${k.tipo}">${esc(k.etiqueta)}</span>
          <span class="gr-etq dato">${p.hechos_nuevos?.length ? `+${p.hechos_nuevos.length} datos nuevos` : "0 datos nuevos"}</span></div>
        ${d.titulo ? `<p class="gr-titulo">${d.url ? `<a href="${esc(d.url)}" target="_blank" rel="noopener">“${esc(d.titulo)}”</a>` : `“${esc(d.titulo)}”`}</p>` : ""}
        <p class="gr-motivo">${madre ? `Deriva de <a href="#" data-ir-nodo="${esc(p.deriva_de)}">${esc(madre)}</a>: ` : ""}${esc(p.motivo || "")}${p.nota_fecha ? `. <b>Fecha imposible:</b> ${esc(p.nota_fecha)}` : ""}</p>
        <p class="gr-tenue">Publicado: ${esc(hora(p.fecha) || "sin fecha")} · ${p.hechos?.length || 0} datos en total</p>`;
    };
    contenedor.addEventListener("click", (ev) => {
      const n = ev.target.closest(".gr-nodo");
      if (n) { mostrar(n.dataset.id); return; }
      const ir = ev.target.closest("[data-ir-nodo]");
      if (ir) { ev.preventDefault(); mostrar(ir.dataset.irNodo); }
    });
    contenedor.addEventListener("keydown", (ev) => { const n = ev.target.closest(".gr-nodo"); if (n && ev.key === "Enter") mostrar(n.dataset.id); });
    const inicial = paginas.find((p) => res.pagina_actual && docs[p.id]?.url === res.pagina_actual) || paginas[0];
    mostrar(inicial.id);
  }

  const raiz = typeof globalThis !== "undefined" ? globalThis : window;
  Object.assign(raiz, { ecoAgente, ecoBitacora, ecoGrafo });
})();
