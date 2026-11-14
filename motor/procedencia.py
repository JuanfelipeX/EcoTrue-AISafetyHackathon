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
MAX_BYTES_IMAGEN = 20 * 1024 * 1024
MAX_BYTES_VIDEO = 60 * 1024 * 1024
TIPOS_MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
              ".heic": "image/heic", ".heif": "image/heif", ".avif": "image/avif", ".gif": "image/gif",
              ".tif": "image/tiff", ".tiff": "image/tiff",
              ".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime", ".avi": "video/x-msvideo"}

# Nombres de herramientas de generación que aparecen en metadatos (EXIF, XMP, PNG, etiquetas de video, C2PA).
GENERADORES_IA = ("midjourney", "stable diffusion", "stablediffusion", "dall-e", "dall·e", "dalle", "openai", "chatgpt",
                  "sora", "firefly", "imagen", "veo", "gemini", "nano banana", "leonardo", "ideogram", "flux",
                  "comfyui", "automatic1111", "novelai", "runway", "pika", "kling", "luma", "dream machine",
                  "hailuo", "synthesia", "heygen", "elevenlabs", "grok", "aurora", "recraft", "krea")


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
    generadores = [g.get("name", "") for g in activo.get("claim_generator_info", []) if isinstance(g, dict)]
    info["generador"] = " ".join(filter(None, generadores + [activo.get("claim_generator") or ""])) or None
    info["emisor"] = firma.get("issuer")
    info["codigos"] = [v.get("code") for v in store.get("validation_status", []) if v.get("code")]
    for a in activo.get("assertions", []):
        etiqueta, datos_a = a.get("label", ""), a.get("data", {})
        if etiqueta.startswith("c2pa.actions"):
            for acc in datos_a.get("actions", []):
                info["acciones"].append(acc.get("action"))
                agente = acc.get("softwareAgent")
                if agente:
                    nombre_agente = agente.get("name") if isinstance(agente, dict) else str(agente)
                    info["generador"] = " ".join(filter(None, [info.get("generador"), nombre_agente]))
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


def _menciona_generador(texto):
    t = (texto or "").lower()
    return next((g for g in GENERADORES_IA if g in t), None)


def senales_ia(datos, mime="image/jpeg", c2pa_info=None):
    """Señales de que una imagen o un video fue generado con IA, leídas de sus metadatos (sin modelos de píxeles).

    Cada señal: {"fuente", "detalle", "fuerza"} con fuerza "declarada" (el archivo dice que es IA) o "indicio"
    (menciona una herramienta de IA, que también se usa para editar). La ausencia de señales NO prueba que sea real:
    los metadatos se borran al reenviar o al hacer una captura de pantalla.
    """
    senales = []
    if c2pa_info:
        if c2pa_info.get("generada_por_ia"):
            senales.append({"fuente": "C2PA", "detalle": f"tipo de origen digital: {c2pa_info.get('fuente_digital')}",
                            "fuerza": "declarada"})
        g = _menciona_generador(" ".join(filter(None, [c2pa_info.get("generador"), c2pa_info.get("firmante")])))
        if g:
            senales.append({"fuente": "C2PA", "detalle": f"herramienta registrada en el manifiesto: {g}", "fuerza": "indicio"})

    # IPTC DigitalSourceType en XMP (Google, Meta, Adobe y otros lo escriben aunque no haya C2PA).
    bajo = datos[:4 * 1024 * 1024].lower() if mime.startswith("image/") else datos.lower()
    for termino in (b"trainedalgorithmicmedia", b"compositewithtrainedalgorithmicmedia", b"compositesynthetic"):
        if b"digitalsourcetype" in bajo and termino in bajo and not (c2pa_info or {}).get("generada_por_ia"):
            senales.append({"fuente": "XMP / IPTC", "detalle": f"DigitalSourceType = {termino.decode()}",
                            "fuerza": "declarada"})
            break

    if mime.startswith("image/"):
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(datos))
            exif = img.getexif()
            for tag, nombre in ((305, "Software"), (270, "ImageDescription"), (315, "Artist"), (37510, "UserComment")):
                valor = exif.get(tag)
                g = _menciona_generador(str(valor)) if valor else None
                if g:
                    senales.append({"fuente": f"EXIF {nombre}", "detalle": f"{str(valor)[:80]}", "fuerza": "indicio"})
            for clave, valor in (img.info or {}).items():
                if not isinstance(valor, str):
                    continue
                if clave.lower() in ("parameters", "prompt", "workflow", "sd-metadata", "dream", "comment", "software",
                                     "description", "ai_metadata"):
                    g = _menciona_generador(valor)
                    if clave.lower() in ("parameters", "prompt", "workflow", "sd-metadata", "dream"):
                        senales.append({"fuente": f"PNG texto «{clave}»",
                                        "detalle": "parámetros de generación (Stable Diffusion / ComfyUI): " + valor[:90],
                                        "fuerza": "declarada"})
                    elif g:
                        senales.append({"fuente": f"PNG texto «{clave}»", "detalle": valor[:90], "fuerza": "indicio"})
        except Exception:
            pass
    elif mime.startswith("video/"):
        for etiqueta, valor in _etiquetas_video(datos).items():
            g = _menciona_generador(valor)
            if g:
                senales.append({"fuente": f"etiqueta de video «{etiqueta}»", "detalle": valor[:90], "fuerza": "indicio"})
    vistos, unicas = set(), []
    for s_ in senales:
        clave = (s_["fuente"], s_["detalle"])
        if clave not in vistos:
            vistos.add(clave)
            unicas.append(s_)
    return unicas


def _etiquetas_video(datos):
    """Etiquetas del contenedor y de las pistas (codificador, comentario, handler…) con ffprobe, si está instalado."""
    import shutil
    import subprocess
    import tempfile
    if not shutil.which("ffprobe"):
        return {}
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(datos)
        ruta = tmp.name
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", ruta],
                           capture_output=True, timeout=30)
        d = json.loads(r.stdout or b"{}")
    except Exception:
        return {}
    finally:
        Path(ruta).unlink(missing_ok=True)
    etiquetas = {}
    for k, v in (d.get("format", {}).get("tags") or {}).items():
        etiquetas[k] = str(v)
    for i, st in enumerate(d.get("streams", [])):
        for k, v in (st.get("tags") or {}).items():
            etiquetas[f"pista{i}.{k}"] = str(v)
    return etiquetas


def resumen_ia(senales):
    if any(x["fuerza"] == "declarada" for x in senales):
        return "declarada", "El archivo declara que fue generado (o compuesto) con IA."
    if senales:
        return "indicio", "Menciona una herramienta de IA en sus metadatos: pudo generarse o solo editarse con ella."
    return "sin_senales", ("No hay señales de IA en los metadatos. Eso no prueba que sea real: los metadatos se borran "
                           "al reenviar o al hacer una captura de pantalla.")


def tipo_por_contenido(datos):
    """Tipo MIME por los primeros bytes (para URLs sin extension)."""
    if datos[:3] == bytes([0xFF, 0xD8, 0xFF]):
        return "image/jpeg"
    if datos[:8] == bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]):
        return "image/png"
    if datos[:4] == b"RIFF" and datos[8:12] == b"WEBP":
        return "image/webp"
    if datos[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if datos[4:8] == b"ftyp":
        marca = datos[8:12]
        if marca in (b"heic", b"heix", b"mif1", b"msf1"):
            return "image/heic"
        if marca in (b"avif", b"avis"):
            return "image/avif"
        if marca == b"qt  ":
            return "video/quicktime"
        return "video/mp4"
    return "image/jpeg"


def analizar_archivo(datos, nombre):
    """Procedencia C2PA + señales de IA de una imagen o un video."""
    sufijo = "." + nombre.rsplit(".", 1)[-1].lower() if "." in nombre.rsplit("/", 1)[-1] else ""
    mime = TIPOS_MIME.get(sufijo) or tipo_por_contenido(datos)
    limite = MAX_BYTES_VIDEO if mime.startswith("video/") else MAX_BYTES_IMAGEN
    if len(datos) > limite:
        raise ValueError(f"El archivo supera {limite // (1024 * 1024)} MB.")
    info = verificar(datos, mime)
    info["tipo"] = "video" if mime.startswith("video/") else "imagen"
    info["senales_ia"] = senales_ia(datos, mime, info)
    info["ia"], info["ia_explicacion"] = resumen_ia(info["senales_ia"])
    info["nombre"] = nombre.rsplit("/", 1)[-1]
    info["bytes"] = len(datos)
    if info["tipo"] == "video":
        info["huella"] = None
    else:
        try:
            from . import forense
            info["forense"] = forense.analizar(datos)
        except Exception as e:  # formatos que Pillow no abre (HEIC), imágenes diminutas, etc.
            info["forense"] = {"error": f"No se pudieron aplicar los filtros: {str(e)[:120]}"}
    return info


def _bytes_imagen(url, limite=MAX_BYTES_IMAGEN, _profundidad=0):
    """Imagen del mini-internet desde el disco; si no, descarga protegida (misma política que las páginas)."""
    from urllib.parse import urlparse
    from . import buscador
    from .extraccion import _ABRIDOR, _verificar_destino, URLNoPermitida
    import urllib.request

    url = buscador.normalizar_url(url)
    p = urlparse(url)
    if p.hostname in buscador.HOSTS_LOCALES and p.path.startswith("/ejemplos/"):
        ruta = (buscador.DIR_CORPUS / p.path.lstrip("/")).resolve()
        if buscador.DIR_CORPUS.resolve() in ruta.parents and ruta.exists():
            return ruta.read_bytes()
    if p.hostname in buscador.HOSTS_LOCALES and p.path.startswith("/sitios/"):
        ruta = (buscador.DIR_CORPUS / p.path.lstrip("/")).resolve()
        if buscador.DIR_CORPUS.resolve() in ruta.parents and ruta.exists():
            return ruta.read_bytes()
        raise FileNotFoundError(url)
    _verificar_destino(url)
    peticion = urllib.request.Request(url, headers={"User-Agent": "ECO/0.1 (laboratorio de defensa epistémica)",
                                                    "Accept": "image/*,video/*,*/*;q=0.8"})
    with _ABRIDOR.open(peticion, timeout=20) as r:
        tipo = (r.headers.get("Content-Type") or "").lower()
        datos = r.read(limite + 1)
    if len(datos) > limite:
        raise URLNoPermitida(f"El archivo supera {limite // (1024 * 1024)} MB.")
    if "text/html" in tipo and not _profundidad:
        # Pegaron la dirección de una página: se verifica su imagen principal (og:image).
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
        soup = BeautifulSoup(datos[:2_000_000].decode("utf-8", errors="replace"), "html.parser")
        meta = soup.find("meta", attrs={"property": "og:image"}) or soup.find("meta", attrs={"name": "twitter:image"})
        if not meta or not meta.get("content"):
            raise URLNoPermitida("La dirección es una página web, no una imagen, y no declara una imagen principal.")
        return _bytes_imagen(urljoin(url, meta["content"]), limite, _profundidad=1)
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
