// Movimiento sutil: entrada escalonada de tarjetas, cifras que cuentan y aparición al hacer scroll.
// Todo se desactiva si el sistema pide reducir el movimiento.
(function () {
  const quieto = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (quieto) return;

  function contar(el) {
    if (el.dataset.contado) return;
    const final = parseInt(el.textContent, 10);
    if (!Number.isFinite(final) || final <= 0 || final > 999) return;
    el.dataset.contado = "1";
    const inicio = performance.now(), dur = 650;
    const paso = (t) => {
      const p = Math.min(1, (t - inicio) / dur);
      el.textContent = String(Math.round(final * (1 - Math.pow(1 - p, 3))));
      if (p < 1) requestAnimationFrame(paso);
    };
    el.textContent = "0";
    requestAnimationFrame(paso);
  }

  const visible = new IntersectionObserver((entradas) => {
    entradas.forEach((e) => {
      if (!e.isIntersecting) return;
      e.target.classList.add("aparece");
      e.target.querySelectorAll(".cifra b, .comp .v, .c2pa-cifras b, .kpi b").forEach(contar);
      visible.unobserve(e.target);
    });
  }, { threshold: 0.08 });

  function preparar(raiz) {
    raiz.querySelectorAll(".tarjeta, .veredicto, .comparacion, .pasos li, .intro, .indice-instalar").forEach((el, i) => {
      if (el.dataset.animado) return;
      el.dataset.animado = "1";
      el.classList.add("animable");
      el.style.setProperty("--retardo", `${Math.min(i, 8) * 45}ms`);
      visible.observe(el);
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    preparar(document.body);
    new MutationObserver((cambios) => cambios.forEach((c) => c.addedNodes.forEach((n) => { if (n.nodeType === 1) preparar(n.parentElement || n); })))
      .observe(document.querySelector("main"), { childList: true, subtree: true });
    addEventListener("hashchange", () => document.querySelectorAll(".vista:not([hidden]) .animable").forEach((el) => {
      el.classList.remove("aparece");
      void el.offsetWidth;
      el.classList.add("aparece");
    }));
  });
})();
