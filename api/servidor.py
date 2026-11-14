"""
Servidor de ECO: sirve el panel web, el mini-internet sintético y la API de análisis en el mismo puerto.

Arranque (desde la carpeta eco):
  uvicorn api.servidor:app --port 8765

  http://localhost:8765/                   panel web de ECO (laboratorio, resultados, URLs propias)
  http://localhost:8765/internet           índice del mini-internet sintético
  http://localhost:8765/sitios/...         páginas del mini-internet
  http://localhost:8765/docs               documentación interactiva de la API

Endpoints:
  GET  /api/salud
  GET  /api/modelos                        cadena de modelos configurada y su disponibilidad
  GET  /api/mundos                         mundos del mini-internet (sin las respuestas)
  GET  /api/mundos/{id}/verdad             respuesta correcta de un mundo (para revelar en la demo)
  GET  /api/buscar?q=texto                 mundos del mini-internet parecidos a la consulta
  POST /api/analizar                       {afirmacion, urls, metodo?, modelo?}
  POST /api/analizar_mundo                 {mundo_id, metodo?, modelo?}  ECO + línea base lado a lado
  POST /api/analizar_pagina                {url, seleccion?, metodo?}  (usado por la extensión)
  GET  /api/resultados                     resultados guardados de la evaluación y de la demo del agente
  POST /mcp                                servidor MCP por HTTP (Streamable HTTP) para agentes remotos

Modo público (ECO_MODO_PUBLICO=1, usado en AWS): límite de peticiones por IP, tope diario de llamadas al
modelo, el cliente no puede elegir modelo, y las URLs del mini-internet se devuelven con el dominio público.
"""

import contextlib
import json
import time
from collections import defaultdict, deque
from functools import lru_cache
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from motor import buscador, linea_base
from motor.analisis import analizar_urls
from motor.config import RAIZ_PROYECTO, config
from mcp_eco.servidor import app_http as mcp_http, mcp

@contextlib.asynccontextmanager
async def _ciclo_de_vida(_app):
    async with mcp.session_manager.run():  # el MCP montado en /mcp necesita su gestor de sesiones
        yield


app = FastAPI(title="ECO", description="¿Cuántas fuentes hay de verdad detrás de una afirmación?", version="1.2",
              lifespan=_ciclo_de_vida)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_PETICIONES = defaultdict(deque)


def _ip_cliente(request):
    # Detrás de Cloudflare la IP real llega en CF-Connecting-IP.
    return request.headers.get("cf-connecting-ip") or (request.client.host if request.client else "?")


@app.middleware("http")
async def _modo_publico(request: Request, call_next):
    if not config.modo_publico:
        return await call_next(request)
    if request.method == "POST":
        ventana = _PETICIONES[_ip_cliente(request)]
        ahora = time.time()
        while ventana and ahora - ventana[0] > 60:
            ventana.popleft()
        if len(ventana) >= config.limite_peticiones_minuto:
            return JSONResponse({"detail": "Demasiadas peticiones; espere un minuto."}, status_code=429)
        ventana.append(ahora)
    respuesta = await call_next(request)
    host = (request.headers.get("host") or "").split(":")[0].lower()
    tipo = respuesta.headers.get("content-type", "")
    if host in {h.lower() for h in config.hosts_publicos} and tipo.startswith("application/json"):
        # Las URLs del mini-internet se guardan con la base local; se reescriben al dominio público.
        cuerpo = b"".join([trozo async for trozo in respuesta.body_iterator])
        cuerpo = cuerpo.replace(buscador.URL_BASE_CORPUS.encode(), f"https://{host}".encode())
        cabeceras = {k: v for k, v in respuesta.headers.items() if k.lower() != "content-length"}
        return Response(cuerpo, status_code=respuesta.status_code, headers=cabeceras, media_type=tipo)
    return respuesta


def _modelo_permitido(modelo):
    """En modo público el cliente no elige el modelo (evita gastar en modelos caros o tocar servicios internos)."""
    return None if config.modo_publico else modelo

Metodo = Literal["hibrido", "hechos", "linea_base"]
DIR_CORPUS = buscador.DIR_CORPUS
DIR_WEB = RAIZ_PROYECTO / "web"
DIR_RESULTADOS = RAIZ_PROYECTO / "evaluacion" / "resultados"


class PeticionAnalisis(BaseModel):
    afirmacion: str = Field(..., min_length=3)
    urls: list[str] = Field(..., min_length=1, max_length=40)
    metodo: Metodo = "hibrido"
    modelo: str | None = None


class PeticionMundo(BaseModel):
    mundo_id: str
    metodo: Metodo = "hibrido"
    modelo: str | None = None


class PeticionPagina(BaseModel):
    url: str
    seleccion: str | None = None
    metodo: Metodo = "hibrido"
    modelo: str | None = None


@lru_cache(maxsize=1)
def _verdad():
    gt = json.loads((DIR_CORPUS / "ground_truth.json").read_text(encoding="utf-8"))
    return {e["id"]: e for e in gt["escenarios"]}


def _mundo(mundo_id):
    mundo = next((m for m in buscador._indice() if m["id"] == mundo_id), None)
    if mundo is None:
        raise HTTPException(404, f"No existe el mundo {mundo_id}.")
    return mundo


@app.get("/api/salud")
def salud():
    return {"estado": "ok", "modelo": config.llm_modelo, "respaldo": config.llm_modelos_respaldo,
            "mundos_en_corpus": len(buscador._indice())}


@app.get("/api/modelos")
def modelos():
    """Cadena de modelos del .env y qué proveedores tienen credenciales o están vivos."""
    ollama = []
    try:
        base = config.ollama_base_url.rstrip("/").removesuffix("/v1")
        r = httpx.get(f"{base}/api/tags", timeout=2)
        ollama = [m["name"] for m in r.json().get("models", [])]
    except Exception:
        pass
    proveedores = {
        "openrouter": bool(config.openrouter_api_key),
        "anthropic": bool(config.anthropic_api_key),
        "openai": bool(config.openai_api_key),
        "ollama": bool(ollama),
        "manual": True,
    }
    sugeridos = [config.llm_modelo, *config.llm_modelos_respaldo]
    sugeridos += [f"ollama/{m}" for m in ollama if f"ollama/{m}" not in sugeridos]
    return {"principal": config.llm_modelo, "respaldo": config.llm_modelos_respaldo,
            "proveedores": proveedores, "ollama": ollama, "sugeridos": sugeridos}


@app.get("/api/mundos")
def mundos():
    verdad = _verdad()
    return [{"id": m["id"], "afirmacion": m["afirmacion"], "conjunto": verdad.get(m["id"], {}).get("conjunto", "principal"),
             "paginas": [{"medio": p["medio"], "titulo": p["titulo"], "url": p["url"]} for p in m["paginas"]]}
            for m in buscador._indice()]


@app.get("/api/mundos/{mundo_id}/verdad")
def verdad(mundo_id: str):
    esc = _verdad().get(mundo_id)
    if esc is None:
        raise HTTPException(404, f"No existe el mundo {mundo_id}.")
    return {"id": esc["id"], "tipo": esc["tipo"], "conjunto": esc.get("conjunto"),
            "fuentes_aparentes": esc["fuentes_aparentes"], "fuentes_efectivas_esperadas": esc["fuentes_efectivas_esperadas"],
            "origen": esc["origen"],
            "paginas": [{"id": p["id"], "rol": p["rol"], "deriva_de": p["deriva_de"], "tipo_sitio": p.get("tipo_sitio")}
                        for p in esc["paginas"]]}


@app.get("/api/buscar")
def buscar(q: str, n: int = 5):
    return [{"id": m["id"], "afirmacion": m["afirmacion"], "parecido": m["parecido"],
             "urls": [p["url"] for p in m["paginas"]]} for m in buscador.buscar(q, n)]


@app.post("/api/analizar")
def analizar(p: PeticionAnalisis):
    return analizar_urls(p.afirmacion, p.urls, modelo=_modelo_permitido(p.modelo), metodo=p.metodo)


@app.post("/api/analizar_mundo")
def analizar_mundo(p: PeticionMundo):
    """Análisis de ECO y de la línea base sobre el mismo mundo, para compararlos lado a lado."""
    mundo = _mundo(p.mundo_id)
    urls = [x["url"] for x in mundo["paginas"]]
    res = analizar_urls(mundo["afirmacion"], urls, modelo=_modelo_permitido(p.modelo), metodo=p.metodo)
    documentos = [buscador.cargar(u) for u in urls]
    base = linea_base.analizar(documentos)
    sim = linea_base.matriz_similitud(documentos) if len(documentos) > 1 else [[1.0]]
    res["mundo"] = mundo["id"]
    res["linea_base"] = {"fuentes_efectivas": base["fuentes_efectivas"], "grupos": base["grupos"],
                         "umbral": base["umbral"]}
    res["similitud"] = {"ids": [d.id for d in documentos],
                        "matriz": [[round(float(x), 3) for x in fila] for fila in sim]}
    return res


@app.post("/api/analizar_pagina")
def analizar_pagina(p: PeticionPagina):
    mundo = buscador.mundo_de_url(p.url)
    if mundo is None and p.seleccion:
        candidatos = buscador.buscar(p.seleccion, 1)
        if candidatos and candidatos[0]["parecido"] >= 0.3:
            mundo = candidatos[0]
    if mundo is None:
        raise HTTPException(404, "La página no pertenece al mini-internet de ECO. "
                                 "Para páginas reales use /api/analizar con la afirmación y las URLs.")
    res = analizar_urls(mundo["afirmacion"], [x["url"] for x in mundo["paginas"]], modelo=_modelo_permitido(p.modelo), metodo=p.metodo)
    res["mundo"] = mundo["id"]
    res["pagina_actual"] = buscador.normalizar_url(p.url)
    return res


@app.get("/api/resultados")
def resultados():
    """Resúmenes de evaluacion/resultados: comparación de métodos por modelo y demo del agente."""
    comparaciones, agentes = [], []
    for ruta in sorted(DIR_RESULTADOS.glob("comparacion_*.json")):
        d = json.loads(ruta.read_text(encoding="utf-8"))
        comparaciones.append({"archivo": ruta.name, "modelo": d.get("modelo"), "umbral": d.get("umbral"),
                              "conjunto": d.get("conjunto", "desarrollo"),
                              "resumenes": d.get("resumenes", {}), "errores": len(d.get("errores", [])),
                              "escenarios": [{"id": x["escenario"], "tipo": x["tipo"],
                                              "hibrido": x["evaluacion"]["hibrido"]} for x in d.get("detalle", [])]})
    for ruta in sorted(DIR_RESULTADOS.glob("agente_*.json")):
        filas = json.loads(ruta.read_text(encoding="utf-8"))
        agentes.append({"archivo": ruta.name, "modelo": ruta.stem.removeprefix("agente_"), "filas": filas})
    barrido = None
    if (DIR_RESULTADOS / "linea_base_barrido.json").exists():
        barrido = json.loads((DIR_RESULTADOS / "linea_base_barrido.json").read_text(encoding="utf-8"))
    return {"comparaciones": comparaciones, "agentes": agentes, "barrido_linea_base": barrido}


# ---------------- archivos estáticos ----------------
app.router.routes.extend(mcp_http.routes)  # POST /mcp (sin redirección a /mcp/)
app.mount("/sitios", StaticFiles(directory=DIR_CORPUS / "sitios"), name="sitios")
app.mount("/web", StaticFiles(directory=DIR_WEB), name="web")


@app.get("/internet")
def internet():
    return FileResponse(DIR_CORPUS / "index.html")


@app.get("/")
def panel():
    return FileResponse(DIR_WEB / "index.html")
