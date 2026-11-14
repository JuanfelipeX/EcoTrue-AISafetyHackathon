"""
Noticias reales, en tiempo real.

- analizar_pagina_real(url): la nota que la persona está leyendo, comparada con la cobertura del mismo tema que
  encuentra el buscador (Exa) y con las fuentes que la propia nota cita.
- investigar_tema(tema): la persona escribe un tema o una afirmación; ECO busca noticias recientes y las analiza.

En ambos casos el resultado separa los medios con reportería propia de los que solo repiten a otros. ECO no
califica medios por reputación: ordena por evidencia (quién publicó primero, quién aporta datos propios).
"""

import re
import urllib.parse

from . import busqueda
from .analisis import analizar_documentos
from .extraccion import cargar_desde_url

DOMINIOS_IGNORADOS = ("facebook.", "twitter.", "x.com", "whatsapp.", "linkedin.", "t.me", "instagram.", "tiktok.",
                      "pinterest.", "reddit.com/submit", "google.", "apple.com", "spotify.", "mailto:", "flipboard.",
                      "telegram.", "share", "doubleclick", "googletagmanager", "amazon.", "play.google", "youtube.",
                      "youtu.be", "subscribe", "suscrib", "newsletter", "/login", "/signin", "cookie", "privacy",
                      "privacidad")


# Noticias reales: más páginas y más largas que los mundos del laboratorio; la lista de hechos necesita más espacio.
MAX_TOKENS_WEB = 8000


def _dominio(url):
    return urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")


def enlaces_citados(doc, maximo=4):
    """Enlaces externos del cuerpo de la nota (lo que cita como respaldo), sin redes sociales ni navegación."""
    propio = _dominio(doc.url)
    vistos, salida = set(), []
    for url in doc.enlaces:
        u = url.split("#")[0]
        d = _dominio(u)
        if not d or d == propio or any(x in u.lower() for x in DOMINIOS_IGNORADOS):
            continue
        if urllib.parse.urlparse(u).path in ("", "/"):
            continue
        if u not in vistos:
            vistos.add(u)
            salida.append(u)
        if len(salida) >= maximo:
            break
    return salida


def _consulta(texto):
    """Consulta de búsqueda a partir de un título: sin el nombre del medio al final."""
    t = re.split(r"\s[-|–—]\s", texto or "")[0]
    return t.strip()[:300]


def _documentos_buscados(consulta, n, excluir_url=None, dias=None):
    try:
        resultados = busqueda.buscar(consulta, n=n, dias=dias, excluir=[excluir_url] if excluir_url else None)
    except busqueda.SinBuscador:
        return [], "sin_buscador"
    except Exception as e:
        return [], f"error del buscador: {type(e).__name__}"
    return [busqueda.a_documento(r, i) for i, r in enumerate(resultados, start=1)], None


def _finalizar(res, origenes, problema_buscador):
    res["fuentes"] = busqueda.resumen_fuentes(res)
    res["comparada_con"] = origenes
    if problema_buscador == "sin_buscador":
        res["aviso_buscador"] = "El buscador de noticias no está configurado en este servidor: solo se usaron las fuentes que la nota cita."
    elif problema_buscador:
        res["aviso_buscador"] = f"El buscador no respondió ({problema_buscador}); solo se usaron las fuentes que la nota cita."
    return res


def analizar_pagina_real(url, seleccion=None, urls_extra=None, modelo=None):
    doc = cargar_desde_url(url)
    doc.id = "actual"
    afirmacion = re.sub(r"\s+", " ", (seleccion or "").strip())[:400] or _consulta(doc.titulo) or "Afirmación de la página"
    documentos, vistos = [doc], {doc.url}
    for u in (urls_extra or [])[:6] + enlaces_citados(doc):
        if u in vistos:
            continue
        try:
            d = cargar_desde_url(u)
            d.id = f"cita{len(documentos):02d}"
            documentos.append(d)
            vistos.add(u)
        except Exception:
            continue
    n_citadas = len(documentos) - 1
    buscados, problema = _documentos_buscados(afirmacion, 8, excluir_url=url, dias=45)
    for d in buscados:
        if d.url not in vistos:
            vistos.add(d.url)
            documentos.append(d)
    res = analizar_documentos(documentos, afirmacion, modelo=modelo, max_tokens=MAX_TOKENS_WEB)
    res["modo"] = "pagina_real"
    res["pagina_actual"] = url
    n_busc = len(documentos) - 1 - n_citadas
    if len(documentos) <= 1:
        res["nota_web_real"] = ("Solo se pudo analizar esta página: no se encontró otra cobertura del tema ni fuentes "
                                "citadas que se puedan abrir.")
    else:
        partes = []
        if n_busc:
            partes.append(f"{n_busc} nota{'s' if n_busc != 1 else ''} del mismo tema encontradas con el buscador")
        if n_citadas:
            partes.append(f"{n_citadas} fuente{'s' if n_citadas != 1 else ''} que la nota cita")
        res["nota_web_real"] = "Se comparó esta página con " + " y ".join(partes) + "."
    return _finalizar(res, {"buscador": n_busc, "enlaces_citados": n_citadas}, problema)


def investigar_tema(tema, n=10, dias=30, modelo=None):
    tema = re.sub(r"\s+", " ", (tema or "").strip())[:400]
    if len(tema) < 4:
        raise ValueError("Escribe un tema o una afirmación más concreta.")
    documentos, problema = _documentos_buscados(tema, n, dias=dias)
    if problema == "sin_buscador":
        raise busqueda.SinBuscador("El buscador de noticias no está configurado en este servidor (falta EXA_API_KEY).")
    if not documentos:
        raise ValueError(f"No se encontraron noticias recientes sobre «{tema}» en los últimos {dias} días.")
    res = analizar_documentos(documentos, tema, modelo=modelo, max_tokens=MAX_TOKENS_WEB)
    res["modo"] = "tema"
    res["nota_web_real"] = f"Se analizaron {len(documentos)} noticias de los últimos {dias} días encontradas con el buscador."
    return _finalizar(res, {"buscador": len(documentos)}, problema)
