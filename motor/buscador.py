"""
Buscador simulado del mini-internet y carga de documentos.

En el corpus, cada escenario es un "mundo" aparte: un pequeño internet donde una afirmación
circula de cierta forma. El buscador trabaja dentro de esos mundos:
  - mundo_de_url(url): devuelve el mundo al que pertenece una página.
  - buscar(consulta): devuelve los mundos cuyo tema se parece a la consulta.
Solo usa corpus/indice_busqueda.json (temas y URLs), nunca las respuestas correctas.

cargar(url): si la URL es del mini-internet la lee del disco (rápido y sin red);
si no, la descarga de la web.
"""

import json
from functools import lru_cache
from urllib.parse import urlparse

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .config import RAIZ_PROYECTO, config
from .extraccion import cargar_desde_archivo, cargar_desde_url

DIR_CORPUS = RAIZ_PROYECTO / "corpus"
# El mini-internet se reconoce en cualquier puerto local (el 8000 suele estar ocupado en Windows).
# En el despliegue público también se reconoce el dominio (ECO_HOSTS_PUBLICOS); las URLs se normalizan
# a la base local para que la caché de respuestas del modelo siga sirviendo.
HOSTS_LOCALES = {"localhost", "127.0.0.1", *[h.lower() for h in config.hosts_publicos]}
URL_BASE_CORPUS = "http://localhost:8765"


@lru_cache(maxsize=1)
def _indice():
    ruta = DIR_CORPUS / "indice_busqueda.json"
    if not ruta.exists():
        return []
    return json.loads(ruta.read_text(encoding="utf-8"))


def _ruta_local(url):
    p = urlparse(url)
    if p.hostname not in HOSTS_LOCALES or not p.path.startswith("/sitios/"):
        return None
    ruta = (DIR_CORPUS / p.path.lstrip("/")).resolve()
    if DIR_CORPUS.resolve() not in ruta.parents or not ruta.exists():
        return None
    return ruta


def normalizar_url(url):
    """Unifica 127.0.0.1, localhost y el puerto para que las URLs del corpus coincidan."""
    p = urlparse(url)
    if p.hostname in HOSTS_LOCALES and p.path.startswith("/sitios/"):
        return f"{URL_BASE_CORPUS}{p.path}"
    return url


def cargar(url, id_doc=None):
    url = normalizar_url(url)
    ruta = _ruta_local(url)
    if ruta:
        return cargar_desde_archivo(ruta, url, id_doc or ruta.stem)
    return cargar_desde_url(url, id_doc)


def mundo_de_url(url):
    url = normalizar_url(url)
    for mundo in _indice():
        if any(p["url"] == url for p in mundo["paginas"]):
            return mundo
    return None


def buscar(consulta, max_resultados=5):
    """Mundos del mini-internet ordenados por parecido con la consulta."""
    indice = _indice()
    if not indice or not consulta.strip():
        return []
    textos = [m["afirmacion"] + " " + " ".join(p["titulo"] for p in m["paginas"]) for m in indice]
    vectorizador = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
    matriz = vectorizador.fit_transform(textos + [consulta])
    puntajes = cosine_similarity(matriz[-1], matriz[:-1])[0]
    orden = sorted(range(len(indice)), key=lambda i: -puntajes[i])[:max_resultados]
    return [{**indice[i], "parecido": round(float(puntajes[i]), 3)} for i in orden]
