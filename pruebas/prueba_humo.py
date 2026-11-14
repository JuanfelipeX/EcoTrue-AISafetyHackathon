"""
Prueba de humo de ECO: verifica en un minuto que todas las piezas funcionan.

Uso (desde la carpeta eco):
  python -m pruebas.prueba_humo
  python -m pruebas.prueba_humo --modelo anthropic/claude-haiku-5-5    usa ese modelo en la prueba de la API

Por defecto usa las respuestas guardadas de claudecode/sonnet (no gasta API).
"""

import argparse
import asyncio
import json
import sys

from motor.config import RAIZ_PROYECTO

# Respuestas reales de Claude Sonnet (vía Claude Code) guardadas en .cache/llm: la prueba no gasta API.
MODELO_CACHE = "claudecode/sonnet"
resultados = []


def chequeo(nombre, funcion):
    try:
        detalle = funcion()
        resultados.append((True, nombre, detalle))
    except Exception as e:
        resultados.append((False, nombre, f"{type(e).__name__}: {e}"))


def corpus():
    gt = json.loads((RAIZ_PROYECTO / "corpus" / "ground_truth.json").read_text(encoding="utf-8"))
    paginas = sum(len(e["paginas"]) for e in gt["escenarios"])
    for e in gt["escenarios"]:
        for p in e["paginas"]:
            assert (RAIZ_PROYECTO / "corpus" / "sitios" / e["id"] / f"{p['id']}.html").exists(), p["id"]
    return f"{len(gt['escenarios'])} mundos, {paginas} páginas"


def linea_base():
    from evaluacion.evaluar_linea_base import cargar_escenarios, correr
    _, resumen = correr(cargar_escenarios(), 0.6)
    assert resumen["literal"]["exactitud"] == 1.0
    return f"literal {resumen['literal']['exactitud']:.0%}, paráfrasis {resumen['parafrasis']['exactitud']:.0%}"


def metodo_hechos():
    from evaluacion.evaluar_linea_base import cargar_escenarios, evaluar_escenario
    from motor import hechos
    from motor.llm import ClienteLLM
    cliente = ClienteLLM(modelo=MODELO_CACHE, respaldo=[])
    aciertos = total = 0
    for esc, docs in cargar_escenarios():
        if esc.get("conjunto") != "principal":
            continue
        res = hechos.analizar(docs, esc["afirmacion"], cliente=cliente, umbral_copia=0.6)
        aciertos += evaluar_escenario(esc, res)["exacto"]
        total += 1
    assert aciertos == total, f"{aciertos}/{total}"
    return f"{aciertos}/{total} mundos del conjunto principal (respuestas en caché)"


def api(modelo):
    from fastapi.testclient import TestClient
    from api.servidor import app
    import motor.analisis as analisis
    cliente = TestClient(app)
    assert cliente.get("/api/salud").json()["estado"] == "ok"
    assert cliente.get("/sitios/e01-s1/e01-s1-p01.html").status_code == 200
    original = analisis.ClienteLLM
    analisis.ClienteLLM = lambda modelo_arg=None, **kw: original(modelo=modelo, respaldo=[])
    try:
        r = cliente.post("/api/analizar_pagina", json={"url": "http://localhost:8765/sitios/e01-s1/e01-s1-p03.html"})
    finally:
        analisis.ClienteLLM = original
    datos = r.json()
    assert r.status_code == 200, datos
    assert datos["metodo"] == "hibrido", datos.get("aviso")
    return f"analizar_pagina: {datos['fuentes_aparentes']} páginas -> {datos['fuentes_efectivas']} fuente(s), método {datos['metodo']}"


def mcp():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def probar():
        params = StdioServerParameters(command=sys.executable, args=[str(RAIZ_PROYECTO / "mcp_eco" / "servidor.py")])
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                herramientas = [t.name for t in (await s.list_tools()).tools]
                assert "evaluar_corroboracion" in herramientas
                return herramientas
    return ", ".join(asyncio.run(probar()))


def extension():
    ruta = RAIZ_PROYECTO / "extension"
    manifest = json.loads((ruta / "manifest.json").read_text(encoding="utf-8"))
    for f in ["background.js", "popup.html", "popup.js", "render.js", "config.js", "estilos.css"]:
        assert (ruta / f).exists(), f
    return f"manifest v{manifest['manifest_version']}, archivos completos"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--modelo", default=MODELO_CACHE)
    args = parser.parse_args()
    chequeo("Corpus sintético", corpus)
    chequeo("Línea base", linea_base)
    chequeo("ECO híbrido (caché)", metodo_hechos)
    chequeo(f"API ({args.modelo})", lambda: api(args.modelo))
    chequeo("Servidor MCP", mcp)
    chequeo("Extensión", extension)
    for ok, nombre, detalle in resultados:
        print(f"{'OK   ' if ok else 'FALLA'} {nombre:<32} {detalle}")
    sys.exit(0 if all(ok for ok, _, _ in resultados) else 1)


if __name__ == "__main__":
    main()
