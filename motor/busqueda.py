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


# Dominios de gobiernos y organismos públicos: una fuente primaria (el comunicado) va antes que quien lo cuenta.
_OFICIAL = re.compile(r"(^|\.)(gov|gob|mil|gouv|gc\.ca|europa\.eu|who\.int|un\.org|paho\.org|oas\.org)(\.[a-z]{2})?$"
                      r"|\.gov\.[a-z]{2}$|\.gob\.[a-z]{2}$")


def es_oficial(dominio):
    d = (dominio or "").lower().removeprefix("www.")
    return bool(_OFICIAL.search(d))


def _puntaje(x):
    # Orden: fuente oficial, datos que otros medios independientes confirman, datos propios, foto firmada, quien publicó antes.
    return (x["oficial"], x["corroborados"], x["datos_propios"], x["foto_firmada"], -(x["_orden"]))


def _razones(x, primero, n_grupos):
    r = []
    if x["oficial"]:
        r.append("es la fuente oficial (primaria)")
    if primero and n_grupos > 1:
        r.append("publicó primero")
    elif n_grupos == 1:
        r.append("es el origen: las demás notas la repiten")
    if x["corroborados"]:
        r.append(f"otros medios independientes confirman {x['corroborados']} de sus datos")
    if x["datos_propios"]:
        r.append(f"aporta {x['datos_propios']} dato{'s' if x['datos_propios'] != 1 else ''} propio{'s' if x['datos_propios'] != 1 else ''}")
    if x["foto_firmada"]:
        r.append("usa una foto propia con firma digital (C2PA)")
    return r


def recomendar(propias, n_grupos):
    """La fuente recomendada para leer primero, con razones medibles del propio análisis (no reputación)."""
    if not propias:
        return None
    mejor = propias[0]
    primero = min(propias, key=lambda x: x["_orden"]) is mejor
    return {"sitio": mejor["sitio"], "url": mejor["url"], "titulo": mejor["titulo"], "fecha": mejor["fecha"],
            "oficial": mejor["oficial"], "razones": _razones(mejor, primero, n_grupos),
            "aviso": "Es la mejor fuente para leer sobre este hecho según la evidencia de este análisis, no un sello de "
                     "verdad: un medio con reportería propia también puede equivocarse."}


def resumen_fuentes(res):
    """Fuentes ordenadas por evidencia: primero quien tiene reportería propia (origen de un grupo), por cuántos
    datos propios aporta; luego quienes solo repiten a otros. No es un juicio de reputación del medio."""
    docs = {d["id"]: d for d in res.get("documentos", [])}
    paginas = {p["id"]: p for p in res.get("paginas", [])}
    propias, repiten = [], []
    grupos = res.get("grupos", [])
    for i, g in enumerate(grupos):
        o = docs.get(g["origen"], {})
        pag = paginas.get(g["origen"], {})
        corro = sum(1 for h in res.get("hechos", []) if h.get("fuentes_independientes", 0) >= 2 and g["origen"] in h.get("grupos", []))
        firmada = any(im.get("estado") == "confiable" and not im.get("generada_por_ia") for im in pag.get("imagenes", []) or [])
        propias.append({"sitio": g.get("origen_sitio"), "url": o.get("url"), "titulo": o.get("titulo"),
                        "fecha": g.get("origen_fecha"), "datos_propios": len(g.get("aporte", [])),
                        "corroborados": corro, "foto_firmada": firmada,
                        "oficial": es_oficial(o.get("dominio") or pag.get("dominio") or g.get("origen_sitio")), "_orden": i,
                        "lo_repiten": [docs.get(m, {}).get("sitio", m) for m in g["miembros"] if m != g["origen"]]})
        for m in g["miembros"]:
            if m == g["origen"]:
                continue
            d = docs.get(m, {})
            repiten.append({"sitio": d.get("sitio"), "url": d.get("url"), "titulo": d.get("titulo"),
                            "repite_a": g.get("origen_sitio"), "motivo": paginas.get(m, {}).get("motivo")})
    propias.sort(key=_puntaje, reverse=True)
    recomendada = recomendar(propias, len(grupos))
    for x in propias:
        x.pop("_orden", None)
    return {"recomendada": recomendada, "con_reporteria_propia": propias, "solo_repiten": repiten}
