"""
Análisis de una noticia real (fuera del mini-internet), en tiempo real.

Sin buscador, ECO compara la página con:
  1. las fuentes que la propia nota cita (sus enlaces externos): ¿se apoya en fuentes independientes o en copias?
  2. las pestañas que la persona eligió en la extensión (otras notas sobre el mismo tema).
  3. opcional: resultados de un buscador con licencia para uso por API (BRAVE_SEARCH_API_KEY, plan gratuito de
     Brave Search API). No se usan RSS ni páginas de resultados de buscadores cuyos términos lo prohíben.
"""

import json
import os
import re
import urllib.parse
import urllib.request

from .analisis import analizar_urls
from .extraccion import cargar_desde_url

DOMINIOS_IGNORADOS = ("facebook.", "twitter.", "x.com", "whatsapp.", "linkedin.", "t.me", "instagram.", "tiktok.",
                      "pinterest.", "reddit.com/submit", "google.", "apple.com", "spotify.", "mailto:", "flipboard.",
                      "telegram.", "share", "doubleclick", "googletagmanager", "amazon.", "play.google", "youtube.",
                      "youtu.be", "subscribe", "suscrib", "newsletter", "/login", "/signin", "cookie", "privacy",
                      "privacidad")
MAX_CANDIDATAS = 10


def _dominio(url):
    return urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")


def enlaces_citados(doc, maximo=6):
    """Enlaces externos del cuerpo de la nota (lo que cita como respaldo), sin redes sociales ni navegación."""
    propio = _dominio(doc.url)
    vistos, salida = set(), []
    for url in doc.enlaces:
        u = url.split("#")[0]
        d = _dominio(u)
        if not d or d == propio or any(x in u.lower() for x in DOMINIOS_IGNORADOS):
            continue
        if urllib.parse.urlparse(u).path in ("", "/"):
            continue  # portada de un sitio, no una nota
        if u not in vistos:
            vistos.add(u)
            salida.append(u)
        if len(salida) >= maximo:
            break
    return salida


def buscar_cobertura(consulta, maximo=6):
    """Brave Search API (requiere BRAVE_SEARCH_API_KEY). Devuelve [] si no está configurada o falla."""
    clave = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
    if not clave or not consulta:
        return []
    q = urllib.parse.urlencode({"q": consulta[:300], "count": maximo, "search_lang": "es"})
    req = urllib.request.Request(f"https://api.search.brave.com/res/v1/news/search?{q}",
                                 headers={"Accept": "application/json", "X-Subscription-Token": clave})
    try:
        datos = json.load(urllib.request.urlopen(req, timeout=15))
    except Exception:
        return []
    return [r["url"] for r in datos.get("results", []) if r.get("url")][:maximo]


def analizar_pagina_real(url, seleccion=None, urls_extra=None, modelo=None):
    doc = cargar_desde_url(url)
    afirmacion = re.sub(r"\s+", " ", (seleccion or "").strip())[:400] or doc.titulo or "Afirmación de la página"
    extra = [u for u in (urls_extra or []) if u.startswith("http") and u != url][:8]
    citadas = enlaces_citados(doc)
    buscadas = buscar_cobertura(doc.titulo or afirmacion)
    candidatas, vistos = [], {url}
    for u in extra + citadas + buscadas:
        if u not in vistos:
            vistos.add(u)
            candidatas.append(u)
    candidatas = candidatas[:MAX_CANDIDATAS]
    res = analizar_urls(afirmacion, [url] + candidatas, modelo=modelo)
    res["modo"] = "pagina_real"
    res["pagina_actual"] = url
    res["comparada_con"] = {"pestanas": len(extra), "enlaces_citados": len(citadas), "buscador": len(buscadas)}
    if res["fuentes_aparentes"] <= 1:
        res["nota_web_real"] = ("Solo se pudo analizar esta página: no cita fuentes externas que se puedan abrir. "
                                "Abre otras noticias sobre el mismo tema en pestañas y usa «Comparar con pestañas abiertas» "
                                "en el ícono de ECO.")
    else:
        partes = []
        if extra:
            partes.append(f"{len(extra)} pestaña{'s' if len(extra) != 1 else ''} que elegiste")
        if citadas:
            partes.append(f"{len(citadas)} fuente{'s' if len(citadas) != 1 else ''} que la nota cita")
        if buscadas:
            partes.append(f"{len(buscadas)} resultado{'s' if len(buscadas) != 1 else ''} del buscador")
        res["nota_web_real"] = "Se comparó esta página con " + " y ".join(partes) + "."
    return res
