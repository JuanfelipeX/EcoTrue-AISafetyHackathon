"""
Punto de entrada único del análisis, usado por la API, el servidor MCP y la demo del agente.

analizar_urls(afirmacion, urls) carga las páginas y aplica ECO híbrido. Si el LLM no está
disponible, cae a la línea base y lo dice en el resultado, para que la demo nunca quede en blanco.
"""

import os

from . import hechos as metodo_hechos
from . import procedencia as modulo_procedencia
from . import linea_base
from .buscador import cargar
from .config import config
from .llm import ClienteLLM, ErrorLLM


def _fecha_corta(iso):
    return iso[:16].replace("T", " ") if iso else "sin fecha"


def resumen_texto(res):
    """Explicación en lenguaje sencillo, para personas y para agentes."""
    n, k = res["fuentes_aparentes"], res["fuentes_efectivas"]
    if n == 0:
        return "No se pudo cargar ninguna página."
    if n == 1:
        return ("Solo hay una página para analizar: no se puede medir independencia con una sola fuente. "
                "ECO mide independencia de fuentes, no veracidad.")
    lineas = [f"{n} páginas analizadas, {k} fuente{'s' if k != 1 else ''} independiente{'s' if k != 1 else ''}."]
    if k == 1 and n > 1:
        g = res["grupos"][0]
        lineas.append(f"Todas parecen venir de un mismo origen: {g['origen_sitio']} ({_fecha_corta(g['origen_fecha'])}). "
                      f"La repetición no es evidencia adicional.")
    elif k < n:
        lineas.append(f"{n - k} páginas repiten lo que ya habían publicado otras, sin aportar datos propios.")
    else:
        lineas.append("Cada página aporta información propia: la cobertura parece independiente.")
    if res.get("hechos"):
        corroborados = [h for h in res["hechos"] if h["fuentes_independientes"] >= 2]
        solos = [h for h in res["hechos"] if h["fuentes_independientes"] < 2]
        lineas.append(f"Datos respaldados por 2 o más fuentes independientes: {len(corroborados)}. "
                      f"Datos que dependen de una sola fuente: {len(solos)}.")
    if res.get("aviso"):
        lineas.append(res["aviso"])
    lineas.append("ECO mide independencia de fuentes, no veracidad: varias fuentes independientes también pueden equivocarse.")
    return " ".join(lineas)


def analizar_documentos(documentos, afirmacion, modelo=None, metodo="hibrido", max_tokens=None):
    if metodo == "linea_base":
        res = linea_base.analizar(documentos)
    else:
        try:
            cliente = ClienteLLM(modelo=modelo, max_tokens=max_tokens) if modelo else ClienteLLM(max_tokens=max_tokens)
            umbral = config.umbral_similitud if metodo == "hibrido" else None
            proc = None
            if os.getenv("ECO_PROCEDENCIA", "1") == "1" and any(getattr(d, "imagenes", None) for d in documentos):
                proc = modulo_procedencia.analizar_documentos(documentos)
            res = metodo_hechos.analizar(documentos, afirmacion, cliente=cliente, umbral_copia=umbral,
                                         procedencia=proc)
        except ErrorLLM as e:
            res = linea_base.analizar(documentos)
            res["aviso"] = ("Aviso: el modelo de lenguaje no respondió, se usó solo similitud de texto, "
                            "que no detecta paráfrasis. Detalle: " + " ".join(l.strip() for l in str(e).splitlines()[:3]))
    res["afirmacion"] = afirmacion
    res["documentos"] = [d.resumen() for d in documentos]
    res["resumen"] = resumen_texto(res)
    return res


def analizar_urls(afirmacion, urls, modelo=None, metodo="hibrido"):
    documentos, errores = [], []
    vistos = set()
    for url in urls:
        try:
            d = cargar(url)
        except Exception as e:  # una URL caída no debe tumbar el análisis
            errores.append({"url": url, "error": f"{type(e).__name__}: {e}"})
            continue
        if d.url in vistos:
            continue
        vistos.add(d.url)
        documentos.append(d)
    res = analizar_documentos(documentos, afirmacion, modelo=modelo, metodo=metodo)
    res["urls_con_error"] = errores
    return res
