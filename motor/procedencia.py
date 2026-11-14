"""
Procedencia criptográfica de las imágenes (C2PA) y huella visual.

Para cada imagen de una página responde:
  - estado: "confiable" (firma válida de un emisor de la lista de confianza), "valida_no_confiable"
    (firma íntegra pero de un emisor desconocido), "rota" (la imagen cambió después de firmarse) o "ausente".
  - firmante, fecha de publicación firmada, si se declara generada por IA y las acciones registradas.
  - huella: hash perceptual (dHash de 64 bits). Sobrevive a la recompresión que borra los metadatos
    (como al reenviar por WhatsApp), así que permite reconocer la misma foto sin firma.

ECO usa esto de dos formas (ver hechos.analizar):
  1. Fecha firmada: una página no pudo publicarse antes que la foto firmada que usa.
  2. Foto ajena: si una página usa una foto firmada por otro medio del conjunto que publicó antes,
     y no tiene foto propia firmada, depende de ese medio.

Límites: C2PA prueba procedencia, no falsedad. La ausencia de firma no significa nada (casi todo el contenido
real no la trae). La lista de confianza de este laboratorio es una CA de demostración; en producción se usa la
lista oficial de C2PA y un sello de tiempo RFC 3161 en vez de la fecha que declara el firmante.
"""

import io
import json
import os
from functools import lru_cache
from pathlib import Path

from .config import RAIZ_PROYECTO

DIR_PKI = RAIZ_PROYECTO / "corpus" / "c2pa"
ETIQUETA_PUBLICACION = "org.eco.publicacion"
FUENTE_IA = ("trainedAlgorithmicMedia", "compositeWithTrainedAlgorithmicMedia", "algorithmicMedia")
MAX_BYTES_IMAGEN = 8 * 1024 * 1024
TIPOS_MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


@lru_cache(maxsize=1)
def anclas_de_confianza():
    """CA de demostración del laboratorio + anclas extra opcionales (ECO_C2PA_ANCLAS: ruta a un PEM)."""
    pem = ""
    ca = DIR_PKI / "ca.pem"
    if ca.exists():
        pem += ca.read_text(encoding="utf-8")
    extra = os.getenv("ECO_C2PA_ANCLAS", "").strip()
    if extra and Path(extra).exists():
        pem += "\n" + Path(extra).read_text(encoding="utf-8")
    return pem


def huella(datos):
    """dHash de 64 bits en hexadecimal (None si no es una imagen legible)."""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(datos)).convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    except Exception:
        return None
    px = list(img.getdata())
    bits = 0
    for fila in range(8):
        for col in range(8):
            bits = (bits << 1) | (px[fila * 9 + col] > px[fila * 9 + col + 1])
    return f"{bits:016x}"


def distancia(h1, h2):
    if not h1 or not h2:
        return 64
    return bin(int(h1, 16) ^ int(h2, 16)).count("1")


def verificar(datos, mime="image/jpeg"):
    """Lee y valida el manifiesto C2PA de una imagen. Nunca lanza: devuelve estado 'ausente' o 'error'."""
    info = {"estado": "ausente", "firmante": None, "emisor": None, "fecha_firmada": None, "medio_declarado": None,
            "generada_por_ia": False, "fuente_digital": None, "acciones": [], "codigos": [], "huella": huella(datos)}
    try:
        import c2pa
    except ImportError:
        info["estado"] = "error"
        info["codigos"] = ["c2pa-python no está instalado"]
        return info
    ajustes = {"verify": {"verify_trust": True}}
    anclas = anclas_de_confianza()
    if anclas:
        ajustes["trust"] = {"trust_anchors": anclas}
    try:
        with c2pa.Context(c2pa.Settings.from_dict(ajustes)) as ctx, \
                c2pa.Reader(mime, io.BytesIO(datos), context=ctx) as lector:
            estado = str(lector.get_validation_state())
            store = json.loads(lector.json())
    except Exception as e:
        if "ManifestNotFound" in type(e).__name__ or "ManifestNotFound" in str(e) or "JUMBF" in str(e):
            return info
        info["estado"] = "error"
        info["codigos"] = [f"{type(e).__name__}: {str(e)[:120]}"]
        return info

    activo = store.get("manifests", {}).get(store.get("active_manifest"), {})
    firma = activo.get("signature_info") or {}
    info["firmante"] = firma.get("common_name")
    info["emisor"] = firma.get("issuer")
    info["codigos"] = [v.get("code") for v in store.get("validation_status", []) if v.get("code")]
    for a in activo.get("assertions", []):
        etiqueta, datos_a = a.get("label", ""), a.get("data", {})
        if etiqueta.startswith("c2pa.actions"):
            for acc in datos_a.get("actions", []):
                info["acciones"].append(acc.get("action"))
                fuente = acc.get("digitalSourceType") or ""
                if fuente:
                    info["fuente_digital"] = fuente.rsplit("/", 1)[-1]
                    info["generada_por_ia"] = info["generada_por_ia"] or info["fuente_digital"] in FUENTE_IA
        elif etiqueta == ETIQUETA_PUBLICACION:
            info["fecha_firmada"] = datos_a.get("fecha")
            info["medio_declarado"] = datos_a.get("medio")

    if estado == "Trusted":
        info["estado"] = "confiable"
    elif estado == "Valid":
        info["estado"] = "valida_no_confiable"
    else:
        info["estado"] = "rota"
    return info


def _bytes_imagen(url):
    """Imagen del mini-internet desde el disco; si no, descarga protegida (misma política que las páginas)."""
    from urllib.parse import urlparse
    from . import buscador
    from .extraccion import _ABRIDOR, _verificar_destino, URLNoPermitida
    import urllib.request

    url = buscador.normalizar_url(url)
    p = urlparse(url)
    if p.hostname in buscador.HOSTS_LOCALES and p.path.startswith("/sitios/"):
        ruta = (buscador.DIR_CORPUS / p.path.lstrip("/")).resolve()
        if buscador.DIR_CORPUS.resolve() in ruta.parents and ruta.exists():
            return ruta.read_bytes()
        raise FileNotFoundError(url)
    _verificar_destino(url)
    peticion = urllib.request.Request(url, headers={"User-Agent": "ECO/0.1 (laboratorio de defensa epistémica)"})
    with _ABRIDOR.open(peticion, timeout=15) as r:
        datos = r.read(MAX_BYTES_IMAGEN + 1)
    if len(datos) > MAX_BYTES_IMAGEN:
        raise URLNoPermitida("La imagen supera el tamaño permitido")
    return datos


def analizar_documentos(documentos, max_por_pagina=4):
    """{id_pagina: [info de cada imagen]} para las páginas que tienen imágenes."""
    resultado = {}
    for d in documentos:
        infos = []
        for url in getattr(d, "imagenes", [])[:max_por_pagina]:
            sufijo = Path(url.split("?")[0]).suffix.lower()
            try:
                info = verificar(_bytes_imagen(url), TIPOS_MIME.get(sufijo, "image/jpeg"))
            except Exception as e:
                info = {"estado": "error", "codigos": [f"{type(e).__name__}: {str(e)[:100]}"], "huella": None,
                        "firmante": None, "fecha_firmada": None, "generada_por_ia": False, "acciones": []}
            info["url"] = url
            infos.append(info)
        if infos:
            resultado[d.id] = infos
    return resultado
