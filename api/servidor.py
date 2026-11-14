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
  GET  /descargas/eco-extension.zip        la extensión de Chrome lista para instalar
  POST /api/analizar_audio                 {url} o {datos_base64, nombre}: ¿voz clonada? (C2PA + AASIST-L)
  POST /api/investigar                     {tema, dias?}: busca noticias (Exa) y separa reportería propia de repetición
  POST /api/verificar_archivo?nombre=x.mp4 cuerpo binario: imagen o video → C2PA + señales de IA
  POST /api/verificar_imagen               {url} o {datos_base64, nombre}: procedencia C2PA de una imagen
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
async def _cabeceras_cache(request: Request, call_next):
    """Cloudflare guarda .js/.css/.zip por 4 h si el origen no dice nada. El panel y la extensión cambian con cada
    despliegue: los recursos versionados (?v=) se pueden guardar; lo demás se revalida siempre."""
    respuesta = await call_next(request)
    ruta = request.url.path
    if ruta.startswith("/web/") and request.url.query.startswith("v="):
        respuesta.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif ruta.startswith(("/web/", "/api/", "/descargas/", "/mcp")) or ruta == "/":
        respuesta.headers["Cache-Control"] = "no-store" if ruta.startswith(("/api/", "/descargas/", "/mcp")) else "no-cache"
    return respuesta


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


ETIQUETAS_MODELO = {"haiku": ("Rápido", "Claude Haiku: responde en segundos; un poco menos fino con paráfrasis."),
                    "sonnet": ("Preciso", "Claude Sonnet: el que usamos para medir los resultados de ECO."),
                    "opus": ("Máximo", "Claude Opus: el más capaz y el más costoso.")}


def _modelos_para_clientes():
    """Modelos que un visitante puede elegir: solo los que el servidor ya tiene configurados y operativos."""
    salida = []
    for m in [config.llm_modelo, *config.llm_modelos_respaldo]:
        if m.startswith(("claudecode/", "manual/", "ollama/")) and config.modo_publico:
            continue
        familia = next((f for f in ETIQUETAS_MODELO if f in m.lower()), None)
        if familia and all(x["id"] != m and x["etiqueta"] != ETIQUETAS_MODELO[familia][0] for x in salida):
            etiqueta, detalle = ETIQUETAS_MODELO[familia]
            salida.append({"id": m, "etiqueta": etiqueta, "detalle": detalle})
    return salida


def _modelo_permitido(modelo):
    """En modo público el cliente solo puede elegir entre los modelos configurados en el servidor."""
    if not config.modo_publico:
        return modelo
    return modelo if modelo and any(x["id"] == modelo for x in _modelos_para_clientes()) else None


# Informes: cada análisis queda disponible un tiempo para abrirlo completo en el panel (#informe/<id>).
_INFORMES = {}


def _guardar_informe(res, url=None):
    import uuid
    if len(_INFORMES) > 400:
        for clave in list(_INFORMES)[:100]:
            _INFORMES.pop(clave, None)
    ident = uuid.uuid4().hex[:12]
    res["informe_id"] = ident
    if url:
        res.setdefault("pagina_actual", url)
    _INFORMES[ident] = res
    return res

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


class PeticionImagen(BaseModel):
    url: str | None = None
    datos_base64: str | None = Field(None, max_length=12_000_000)
    nombre: str | None = None


class PeticionTema(BaseModel):
    tema: str = Field(..., min_length=4, max_length=400)
    dias: int = Field(30, ge=1, le=365)
    modelo: str | None = None


class PeticionAgente(BaseModel):
    modo: Literal["tema", "pagina"]
    tema: str | None = Field(None, max_length=400)
    url: str | None = None
    dias: int = Field(30, ge=1, le=365)
    modelo: str | None = None


class PeticionAudio(BaseModel):
    url: str | None = None
    datos_base64: str | None = Field(None, max_length=15_000_000)
    nombre: str | None = None


class PeticionPagina(BaseModel):
    url: str
    seleccion: str | None = None
    urls_extra: list[str] = Field(default_factory=list, max_length=15)
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
    from motor import busqueda
    return {"principal": config.llm_modelo, "respaldo": config.llm_modelos_respaldo,
            "proveedores": proveedores, "ollama": ollama, "sugeridos": sugeridos,
            "para_clientes": _modelos_para_clientes(), "buscador": busqueda.disponible()}


@app.get("/api/informe/{ident}")
def informe(ident: str):
    res = _INFORMES.get(ident)
    if res is None:
        raise HTTPException(404, "Este informe ya no está disponible (se guardan por unas horas). Vuelve a analizar la página.")
    return res


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
    return _guardar_informe(analizar_urls(p.afirmacion, p.urls, modelo=_modelo_permitido(p.modelo), metodo=p.metodo))


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
        # Noticia real: se compara con las fuentes que cita, las pestañas elegidas y (si hay clave) un buscador.
        from motor.extraccion import URLNoPermitida
        from motor.web_real import analizar_pagina_real
        try:
            return _guardar_informe(analizar_pagina_real(p.url, p.seleccion, p.urls_extra,
                                                         modelo=_modelo_permitido(p.modelo)), p.url)
        except URLNoPermitida as e:
            raise HTTPException(400, str(e))
        except Exception as e:
            raise HTTPException(502, f"No se pudo leer la página ({type(e).__name__}). Algunos sitios bloquean "
                                     "lectores automáticos.")
    res = analizar_urls(mundo["afirmacion"], [x["url"] for x in mundo["paginas"]], modelo=_modelo_permitido(p.modelo), metodo=p.metodo)
    res["mundo"] = mundo["id"]
    res["pagina_actual"] = buscador.normalizar_url(p.url)
    return _guardar_informe(res, p.url)


@app.post("/api/verificar_imagen")
def verificar_imagen(p: PeticionImagen):
    """Procedencia C2PA de una imagen (por URL o subida en base64): firmante, fecha firmada, IA, alteraciones."""
    import base64
    from motor import procedencia
    if p.datos_base64:
        try:
            datos = base64.b64decode(p.datos_base64.split(",")[-1], validate=False)
        except Exception:
            raise HTTPException(400, "El archivo no es válido.")
        nombre = p.nombre or "imagen.jpg"
    elif p.url:
        try:
            datos = procedencia._bytes_imagen(p.url, procedencia.MAX_BYTES_VIDEO)
        except Exception as e:
            motivo = str(e)
            if "403" in motivo or "401" in motivo:
                motivo = "el sitio no permite descargas automáticas; descarga el archivo y súbelo aquí"
            raise HTTPException(400, f"No se pudo descargar el archivo: {motivo}")
        nombre = p.url.split("?")[0]
    else:
        raise HTTPException(400, "Envíe una URL o un archivo.")
    try:
        return procedencia.analizar_archivo(datos, nombre)
    except ValueError as e:
        raise HTTPException(413, str(e))


@app.post("/api/investigar")
def investigar(p: PeticionTema):
    """Busca noticias recientes sobre un tema (Exa) y separa reportería propia de repetición."""
    from motor import busqueda
    from motor.web_real import investigar_tema
    try:
        return _guardar_informe(investigar_tema(p.tema, dias=p.dias, modelo=_modelo_permitido(p.modelo)))
    except busqueda.SinBuscador as e:
        raise HTTPException(503, str(e))
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.post("/api/agente")
def agente(p: PeticionAgente):
    """Igual que /api/investigar o /api/analizar_pagina, pero transmite en vivo (text/event-stream) lo que hace el agente:
    qué busca, qué encontró, qué lee, cuánto lleva el modelo y la decisión sobre cada página. Último evento: 'fin'."""
    import queue
    import threading
    from fastapi.responses import StreamingResponse
    from motor import busqueda
    from motor.web_real import analizar_pagina_real, investigar_tema

    cola = queue.Queue()

    def progreso(**evento):
        cola.put(evento)

    def trabajar():
        try:
            if p.modo == "tema":
                res = investigar_tema(p.tema or "", dias=p.dias, modelo=_modelo_permitido(p.modelo), progreso=progreso)
            else:
                if not p.url:
                    raise ValueError("Falta la URL de la página.")
                mundo = buscador.mundo_de_url(p.url)
                if mundo:  # página del mini-internet: sus páginas relacionadas ya son conocidas
                    from motor.web_real import _emitir_decisiones
                    progreso(etapa="buscar", consulta=mundo["afirmacion"], dias=None)
                    for x in mundo["paginas"]:
                        progreso(etapa="encontrada", sitio=x["medio"], titulo=x["titulo"], url=x["url"])
                    progreso(etapa="llm", modelo="(respuestas guardadas del laboratorio)", paginas=len(mundo["paginas"]), palabras="—")
                    res = analizar_urls(mundo["afirmacion"], [x["url"] for x in mundo["paginas"]], modelo=_modelo_permitido(p.modelo))
                    res["mundo"] = mundo["id"]
                    res["pagina_actual"] = buscador.normalizar_url(p.url)
                    progreso(etapa="hechos", n=len(res.get("hechos", [])), modelo=res.get("modelo"), aviso=res.get("aviso"))
                    progreso(etapa="regla", paginas=res["fuentes_aparentes"], independientes=res["fuentes_efectivas"])
                    _emitir_decisiones(res, progreso)
                else:
                    res = analizar_pagina_real(p.url, modelo=_modelo_permitido(p.modelo), progreso=progreso)
            cola.put({"etapa": "fin", "resultado": _guardar_informe(res, p.url)})
        except (busqueda.SinBuscador, ValueError) as e:
            cola.put({"etapa": "error", "texto": str(e)})
        except Exception as e:
            cola.put({"etapa": "error", "texto": f"No se pudo completar el análisis ({type(e).__name__})."})
        cola.put(None)

    threading.Thread(target=trabajar, daemon=True).start()

    def eventos():
        while True:
            try:
                evento = cola.get(timeout=15)
            except queue.Empty:
                yield ": sigo trabajando\n\n"  # mantiene viva la conexión (Cloudflare corta a los 100 s sin datos)
                continue
            if evento is None:
                break
            yield "data: " + json.dumps(evento, ensure_ascii=False, default=str) + "\n\n"

    return StreamingResponse(eventos(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@app.post("/api/verificar_archivo")
async def verificar_archivo(request: Request, nombre: str = "archivo.jpg"):
    """Imagen o video subido como cuerpo binario (hasta 60 MB): procedencia C2PA y señales de IA en metadatos."""
    from motor import procedencia
    datos = await request.body()
    if not datos:
        raise HTTPException(400, "Envíe el archivo en el cuerpo de la petición.")
    try:
        return procedencia.analizar_archivo(datos, nombre)
    except ValueError as e:
        raise HTTPException(413, str(e))


@app.post("/api/analizar_audio")
def analizar_audio(p: PeticionAudio):
    """¿Voz clonada? Primero credenciales C2PA del archivo; si no hay, el detector AASIST-L reentrenado por ECO."""
    import base64
    from motor import procedencia, voz
    if p.datos_base64:
        try:
            datos = base64.b64decode(p.datos_base64.split(",")[-1], validate=False)
        except Exception:
            raise HTTPException(400, "El archivo no es válido.")
        nombre = p.nombre or "audio.webm"
    elif p.url:
        try:
            datos = procedencia._bytes_imagen(p.url)
        except Exception as e:
            raise HTTPException(400, f"No se pudo descargar el audio: {e}")
        nombre = p.url.split("?")[0].rsplit("/", 1)[-1]
    else:
        raise HTTPException(400, "Envíe una URL o un archivo.")
    try:
        return voz.analizar_audio(datos, nombre)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/voz/estado")
def voz_estado():
    from motor import voz
    return {"disponible": voz.disponible(), "calibracion": voz.calibracion()}


@lru_cache(maxsize=1)
def _ejemplos_imagenes():
    """Una imagen de cada caso en los mundos de procedencia del mini-internet."""
    from motor import procedencia
    ejemplos = {}
    for ruta in sorted((DIR_CORPUS / "sitios").glob("*-c*/img/*.jpg")):
        info = procedencia.verificar(ruta.read_bytes())
        caso = ("ia" if info["generada_por_ia"] else "rota" if info["estado"] == "rota"
                else "sin_metadatos" if info["estado"] == "ausente" else "firmada" if info["estado"] == "confiable" else None)
        if caso and caso not in ejemplos:
            ejemplos[caso] = "/" + ruta.relative_to(DIR_CORPUS).as_posix()
        if len(ejemplos) == 4:
            break
    return ejemplos


@app.get("/api/ejemplos_imagenes")
def ejemplos_imagenes():
    return _ejemplos_imagenes()


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
    procedencia = None
    rutas = sorted(DIR_RESULTADOS.glob("procedencia_*.json"))
    if rutas:
        d = json.loads(rutas[-1].read_text(encoding="utf-8"))
        procedencia = {"modelo": d.get("modelo"), "resumenes": d.get("resumenes"), "n": len(d.get("detalle", []))}
    voz = None
    if (DIR_RESULTADOS / "voz_aasist.json").exists():
        voz = json.loads((DIR_RESULTADOS / "voz_aasist.json").read_text(encoding="utf-8"))
    return {"comparaciones": comparaciones, "agentes": agentes, "barrido_linea_base": barrido,
            "procedencia": procedencia, "voz": voz}


# ---------------- archivos estáticos ----------------
app.router.routes.extend(mcp_http.routes)  # POST /mcp (sin redirección a /mcp/)
(RAIZ_PROYECTO / "corpus" / "ejemplos").mkdir(parents=True, exist_ok=True)
app.mount("/ejemplos", StaticFiles(directory=RAIZ_PROYECTO / "corpus" / "ejemplos"), name="ejemplos")
app.mount("/sitios", StaticFiles(directory=DIR_CORPUS / "sitios"), name="sitios")
app.mount("/web", StaticFiles(directory=DIR_WEB), name="web")


@lru_cache(maxsize=1)
def _zip_extension():
    """La carpeta extension/ empaquetada como eco-extension/ (lista para 'Cargar descomprimida')."""
    import io
    import zipfile
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for ruta in sorted((RAIZ_PROYECTO / "extension").rglob("*")):
            if ruta.is_file():
                z.write(ruta, "eco-extension/" + ruta.relative_to(RAIZ_PROYECTO / "extension").as_posix())
    return buffer.getvalue()


@app.get("/descargas/eco-extension.zip")
def descargar_extension():
    return Response(_zip_extension(), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="eco-extension.zip"'})


@app.get("/internet")
def internet():
    return FileResponse(DIR_CORPUS / "index.html")


@app.get("/")
def panel():
    """index.html con los recursos versionados por contenido: un despliegue nuevo nunca usa un app.js viejo
    guardado en la caché de Cloudflare o del navegador."""
    import hashlib
    html = (DIR_WEB / "index.html").read_text(encoding="utf-8")
    for recurso in ("app.js", "app.css", "i18n.js", "dinamico.js", "agente.js", "agente.css"):
        v = hashlib.sha256((DIR_WEB / recurso).read_bytes()).hexdigest()[:10]
        html = html.replace(f'"/web/{recurso}"', f'"/web/{recurso}?v={v}"')
    version_ext = json.loads((RAIZ_PROYECTO / "extension" / "manifest.json").read_text(encoding="utf-8"))["version"]
    html = html.replace('"/descargas/eco-extension.zip"', f'"/descargas/eco-extension.zip?v={version_ext}"')
    import re
    html = re.sub(r'<span id="version-extension">[^<]*</span>', f'<span id="version-extension">{version_ext}</span>', html)
    return Response(html, media_type="text/html; charset=utf-8", headers={"Cache-Control": "no-cache"})
