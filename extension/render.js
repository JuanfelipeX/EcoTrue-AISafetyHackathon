// Dibuja el resultado de ECO como HTML. Lo usan el popup y el panel dentro de la página.
// Es una función pura (texto -> HTML) y escapa todo lo que viene del servidor.

(function () {
  function esc(texto) {
    return String(texto ?? "")
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function fechaCorta(iso) {
    if (!iso) return "sin fecha";
    return iso.slice(0, 16).replace("T", " ");
  }

  function lista(items, max) {
    if (!items || !items.length) return '<p class="eco-vacio">Ninguno.</p>';
    const visibles = items.slice(0, max).map((t) => `<li>${esc(t)}</li>`).join("");
    const resto = items.length > max ? `<li class="eco-mas">y ${items.length - max} más</li>` : "";
    return `<ul>${visibles}${resto}</ul>`;
  }

  function ecoRender(r) {
    const sitios = {};
    (r.documentos || []).forEach((d) => { sitios[d.id] = d.sitio; });
    const actual = (r.documentos || []).find((d) => d.url === r.pagina_actual);
    const n = r.fuentes_aparentes, k = r.fuentes_efectivas;
    const estado = k <= 1 && n > 1 ? "eco-alerta" : (k < n ? "eco-medio" : "eco-ok");

    const grupos = (r.grupos || []).map((g, i) => {
      const copias = g.miembros.filter((m) => m !== g.origen);
      const marcaOrigen = actual && actual.id === g.origen ? ' <span class="eco-aqui">esta página</span>' : "";
      const copiasHtml = copias.map((m) => {
        const aqui = actual && actual.id === m ? ' <span class="eco-aqui">esta página</span>' : "";
        return `<li>${esc(sitios[m] || m)}${aqui}</li>`;
      }).join("");
      return `<div class="eco-grupo">
        <div class="eco-grupo-titulo">Fuente ${i + 1}: <b>${esc(g.origen_sitio)}</b>${marcaOrigen}
          <span class="eco-fecha">${esc(fechaCorta(g.origen_fecha))}</span></div>
        ${copias.length ? `<div class="eco-copias">Repiten esta fuente sin aportar datos propios (${copias.length}):<ul>${copiasHtml}</ul></div>` : ""}
      </div>`;
    }).join("");

    const hechos = r.hechos ? `
      <h3>Datos respaldados por 2 o más fuentes independientes</h3>${lista(r.corroborados, 6)}
      <h3>Datos que dependen de una sola fuente</h3>${lista(r.de_un_solo_origen, 6)}` : "";

    const pr = r.procedencia;
    const notasFecha = (r.paginas || []).filter((p) => p.nota_fecha);
    const procedencia = pr ? `
      <h3>Procedencia de las imágenes (C2PA)</h3>
      <p class="eco-resumen">${pr.imagenes} imágenes · ${pr.firmadas_confiables} con firma confiable` +
      `${pr.por_foto_ajena.length ? ` · ${pr.por_foto_ajena.length === 1 ? "1 página usa" : `${pr.por_foto_ajena.length} páginas usan`} la foto firmada por otro medio` : ""}` +
      `${pr.generadas_por_ia.length ? ` · ${pr.generadas_por_ia.length} declaradas como IA` : ""}` +
      `${pr.firma_rota.length ? ` · ${pr.firma_rota.length} con la firma rota` : ""}.</p>
      ${notasFecha.map((p) => `<p class="eco-aviso"><b>Fecha imposible (${esc(sitios[p.id] || p.id)}):</b> ${esc(p.nota_fecha)}.</p>`).join("")}` : "";

    const metodo = { hibrido: "ECO híbrido (hechos + similitud)", hechos: "ECO por hechos", linea_base: "solo similitud de texto" }[r.metodo] || r.metodo;

    return `<div class="eco-res">
      <div class="eco-cifras ${estado}">
        <div><span class="eco-num">${n}</span><span class="eco-etq">páginas</span></div>
        <div class="eco-flecha">→</div>
        <div><span class="eco-num">${k}</span><span class="eco-etq">fuente${k === 1 ? "" : "s"} independiente${k === 1 ? "" : "s"}</span></div>
      </div>
      <p class="eco-afirmacion">${esc(r.afirmacion)}</p>
      <p class="eco-resumen">${esc(r.resumen)}</p>
      ${r.nota_web_real ? `<p class="eco-resumen"><b>Noticia real.</b> ${esc(r.nota_web_real)}</p>` : ""}
      ${r.aviso ? `<p class="eco-aviso">${esc(r.aviso)}</p>` : ""}
      ${(r.urls_con_error || []).length ? `<p class="eco-pie">${r.urls_con_error.length} enlace(s) no se pudieron leer (el sitio bloquea lectores automáticos o no es una nota).</p>` : ""}
      <h3>Origen de la información</h3>${grupos}
      ${procedencia}
      ${hechos}
      ${r.panel_url ? `<p><a class="eco-enlace" href="${esc(r.panel_url)}" target="_blank" rel="noopener">Ver árbol de origen y matriz de hechos en el panel de ECO ↗</a></p>` : ""}
      <p class="eco-pie">Método: ${esc(metodo)}. ECO no dice si algo es verdad: mide cuánta evidencia independiente lo respalda.</p>
    </div>`;
  }

  const raiz = typeof globalThis !== "undefined" ? globalThis : window;
  raiz.ecoRender = ecoRender;
  raiz.ecoEsc = esc;
  if (typeof module !== "undefined") module.exports = { ecoRender, esc };
})();
