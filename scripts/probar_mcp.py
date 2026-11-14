"""
Prueba de punta a punta del servidor MCP de ECO: lo arranca por stdio como lo haría Claude
Desktop o Claude Code, lista las herramientas y llama a cada una.

Uso (desde la carpeta eco):
  python -m scripts.probar_mcp
  python -m scripts.probar_mcp --modelo manual/claude-opus-5-5-sesion   (sin API, respuestas guardadas)
  python -m scripts.probar_mcp --url https://eco.kibosecondbrain.com/mcp   (servidor remoto por HTTP)
"""

import argparse
import asyncio
import contextlib
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from motor.config import RAIZ_PROYECTO


def _texto(resultado):
    estructurado = getattr(resultado, "structured_content", None) or getattr(resultado, "structuredContent", None)
    if estructurado:
        return estructurado.get("result", estructurado) if isinstance(estructurado, dict) else estructurado
    partes = [c.text for c in resultado.content if getattr(c, "type", "") == "text"]
    try:
        return json.loads("".join(partes))
    except json.JSONDecodeError:
        return "".join(partes)


@contextlib.asynccontextmanager
async def _transporte(modelo, url):
    if url:
        from mcp.client.streamable_http import streamable_http_client
        async with streamable_http_client(url) as flujos:
            yield flujos[0], flujos[1]
        return
    entorno = dict(os.environ, PYTHONIOENCODING="utf-8")
    if modelo:
        entorno["LLM_MODELO"] = modelo
    parametros = StdioServerParameters(command=sys.executable, args=[str(RAIZ_PROYECTO / "mcp_eco" / "servidor.py")],
                                       env=entorno)
    async with stdio_client(parametros) as (lectura, escritura):
        yield lectura, escritura


async def principal(modelo, url=None):
    async with _transporte(modelo, url) as (lectura, escritura):
        async with ClientSession(lectura, escritura) as sesion:
            info = await sesion.initialize()
            servidor = getattr(info, "server_info", None) or getattr(info, "serverInfo")
            version = getattr(info, "protocol_version", None) or getattr(info, "protocolVersion", "")
            print(f"Servidor: {servidor.name} · protocolo {version}")
            herramientas = (await sesion.list_tools()).tools
            print("Herramientas:", ", ".join(h.name for h in herramientas))

            r = _texto(await sesion.call_tool("buscar_en_mini_internet", {"consulta": "mercurio acueducto San Aurelio", "max_resultados": 2}))
            print(f"\nbuscar_en_mini_internet -> {len(r)} mundos; primero: {r[0]['mundo_id']}")

            r = _texto(await sesion.call_tool("analizar_mundo", {"mundo_id": "e01-s1"}))
            print(f"analizar_mundo(e01-s1) -> {r['fuentes_aparentes']} páginas, {r['fuentes_independientes']} fuentes "
                  f"independientes ({r['metodo']})\n  {r['resumen']}")

            urls = [f"http://localhost:8765/sitios/e03-s2/e03-s2-p0{i}.html" for i in range(1, 5)]
            r = _texto(await sesion.call_tool("evaluar_corroboracion", {
                "afirmacion": "Afirmación del mundo e03-s2", "urls": urls}))
            print(f"evaluar_corroboracion(4 URLs de e03-s2) -> {r['fuentes_aparentes']} páginas, "
                  f"{r['fuentes_independientes']} fuentes independientes")
    print(f"\nOK: el servidor MCP responde por {'HTTP en ' + url if url else 'stdio'}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--modelo", help="forzar LLM_MODELO para esta prueba (proveedor/modelo)")
    parser.add_argument("--url", help="probar un servidor MCP remoto por HTTP (por ejemplo https://…/mcp)")
    args = parser.parse_args()
    asyncio.run(principal(args.modelo, args.url))
