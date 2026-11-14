"""
Búsqueda de cobertura periodística con Exa (exa.ai), una API de búsqueda pensada para agentes de IA.

Exa devuelve, además de la URL, el texto de cada nota: ECO no tiene que descargar cada sitio (más rápido y sin
chocar con sitios que bloquean lectores automáticos). Requiere EXA_API_KEY en el entorno.
"""

import datetime as dt
import json
import os
import re
import urllib.parse
import urllib.request

from . import config as _config  # noqa: F401  (carga el .env)
from .extraccion import Documento

URL_EXA = "https://api.exa.ai/search"


class SinBuscador(RuntimeError):
    """No hay clave de Exa configurada."""


def disponible():
    return bool(os.getenv("EXA_API_KEY", "").strip())


def buscar(consulta, n=8, dias=None, excluir=None):
    """Lista de resultados de Exa: [{url, title, publishedDate, author, text}]."""
    clave = os.getenv("EXA_API_KEY", "").strip()
    if not clave:
        raise SinBuscador("Falta EXA_API_KEY: el buscador de noticias no está configurado en este servidor.")
    cuerpo = {"query": consulta[:500], "type": "auto", "category": "news", "numResults": max(1, min(n, 15)),
              "contents": {"text": {"maxCharacters": 4000}}}
    if dias:
        cuerpo["startPublishedDate"] = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=dias)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    if excluir:
        cuerpo["excludeDomains"] = [urllib.parse.urlparse(u).netloc for u in excluir if u]
    req = urllib.request.Request(URL_EXA, data=json.dumps(cuerpo).encode(), method="POST",
                                 headers={"x-api-key": clave, "Content-Type": "application/json",
                                          "User-Agent": "ECO/0.1 (laboratorio de defensa epistémica)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        datos = json.load(r)
    return [x for x in datos.get("results", []) if x.get("url") and (x.get("text") or "").strip()]


def a_documento(resultado, indice):
    """Convierte un resultado de Exa en un Documento de ECO (párrafos del texto, fecha y sitio)."""
    url = resultado["url"]
    dominio = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
    texto = resultado.get("text") or ""
    parrafos = [p.strip() for p in re.split(r"\n\s*\n|\n", texto) if len(p.strip()) > 40][:30]
    fecha = None
    if resultado.get("publishedDate"):
        try:
            fecha = dt.datetime.fromisoformat(resultado["publishedDate"].replace("Z", "+00:00"))
        except ValueError:
            fecha = None
    return Documento(id=f"exa{indice:02d}", url=url, titulo=resultado.get("title") or url, sitio=dominio,
                     dominio=dominio, autor=resultado.get("author") or "", fecha=fecha, parrafos=parrafos,
                     enlaces=[], imagenes=[resultado["image"]] if resultado.get("image") else [])


def resumen_fuentes(res):
    """Fuentes ordenadas por evidencia: primero quien tiene reportería propia (origen de un grupo), por cuántos
    datos propios aporta; luego quienes solo repiten a otros. No es un juicio de reputación del medio."""
    docs = {d["id"]: d for d in res.get("documentos", [])}
    paginas = {p["id"]: p for p in res.get("paginas", [])}
    propias, repiten = [], []
    for g in res.get("grupos", []):
        o = docs.get(g["origen"], {})
        propias.append({"sitio": g.get("origen_sitio"), "url": o.get("url"), "titulo": o.get("titulo"),
                        "fecha": g.get("origen_fecha"), "datos_propios": len(g.get("aporte", [])),
                        "lo_repiten": [docs.get(m, {}).get("sitio", m) for m in g["miembros"] if m != g["origen"]]})
        for m in g["miembros"]:
            if m == g["origen"]:
                continue
            d = docs.get(m, {})
            repiten.append({"sitio": d.get("sitio"), "url": d.get("url"), "titulo": d.get("titulo"),
                            "repite_a": g.get("origen_sitio"), "motivo": paginas.get(m, {}).get("motivo")})
    propias.sort(key=lambda x: -x["datos_propios"])
    return {"con_reporteria_propia": propias, "solo_repiten": repiten}
