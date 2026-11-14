"""
Entradas multimodales: lo que circula por WhatsApp no son enlaces sino capturas de pantalla y notas de voz.

  leer_captura(imagen)     Claude (visión, vía Bedrock) lee el texto de la captura y propone la afirmación a verificar.
  transcribir(audio)       Whisper (faster-whisper, en el servidor) transcribe la nota de voz.
  afirmacion_de(texto)     Un LLM resume el texto en UNA afirmación verificable y una consulta de búsqueda.

Después, la afirmación se investiga como cualquier tema (motor/web_real.investigar_tema) y, además, la captura pasa
por la verificación de procedencia/IA y la nota de voz por el detector de voz sintética.
"""

import base64
import io
import json
import os
import subprocess
import tempfile
from functools import lru_cache

from .config import config
from .llm import ClienteLLM, extraer_json

SISTEMA_AFIRMACION = (
    "Eres un verificador. Te dan un texto (transcripción de una nota de voz o texto leído de una captura de pantalla). "
    "Devuelve SOLO JSON con: \"afirmacion\": la afirmación central verificable, en una frase neutra en español "
    "(sin adjetivos ni opiniones, con quién/qué/dónde/cuándo si aparecen); \"consulta\": 4 a 10 palabras para buscar "
    "noticias sobre ella; \"tipo\": \"noticia\" si afirma un hecho comprobable, \"opinion\" si es opinión, "
    "\"sin_afirmacion\" si no hay nada que verificar; \"alertas\": lista corta de señales de manipulación en el texto "
    "(urgencia, pedido de reenviar, fuente vaga como 'me dijo un amigo', pedido de dinero o datos), en español.")


def _modelo_vision():
    for m in [config.llm_modelo, *config.llm_modelos_respaldo]:
        if m.startswith("bedrock/"):
            return m.split("/", 1)[1]
    return "us.anthropic.claude-sonnet-4-6"


def afirmacion_de(texto, modelo=None):
    texto = (texto or "").strip()[:6000]
    if len(texto) < 8:
        return {"afirmacion": "", "consulta": "", "tipo": "sin_afirmacion", "alertas": []}
    cliente = ClienteLLM(modelo=modelo) if modelo else ClienteLLM()
    datos, _ = cliente.completar_json(f"Texto:\n\"\"\"\n{texto}\n\"\"\"", sistema=SISTEMA_AFIRMACION)
    return {"afirmacion": str(datos.get("afirmacion") or "").strip(), "consulta": str(datos.get("consulta") or "").strip(),
            "tipo": datos.get("tipo") or "noticia", "alertas": [str(a) for a in (datos.get("alertas") or [])][:5]}


def leer_captura(datos, mime="image/png"):
    """Texto visible en la captura (titulares, tuits, mensajes), leído por Claude con visión."""
    import boto3
    from PIL import Image
    img = Image.open(io.BytesIO(datos)).convert("RGB")
    img.thumbnail((1600, 1600))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    cliente = boto3.client("bedrock-runtime", region_name=config.bedrock_region)
    r = cliente.converse(
        modelId=_modelo_vision(),
        system=[{"text": "Transcribe fielmente TODO el texto legible de la imagen (titulares, publicaciones, mensajes, "
                         "nombres de cuentas o medios, fechas). Luego, en una línea aparte que empiece con 'DESCRIPCIÓN:', "
                         "describe en una frase qué muestra la imagen. No inventes texto que no se vea."}],
        messages=[{"role": "user", "content": [{"image": {"format": "png", "source": {"bytes": buf.getvalue()}}},
                                                 {"text": "Transcribe el texto de esta captura."}]}],
        inferenceConfig={"maxTokens": 1500})
    salida = "".join(b.get("text", "") for b in r["output"]["message"]["content"])
    texto, _, descripcion = salida.partition("DESCRIPCIÓN:")
    texto = texto.replace("**Texto transcrito:**", "").replace("---", "").strip()
    return {"texto": texto, "descripcion": descripcion.strip()}


@lru_cache(maxsize=1)
def _whisper():
    from faster_whisper import WhisperModel
    return WhisperModel(os.getenv("ECO_WHISPER", "base"), device="cpu", compute_type="int8",
                        download_root=os.getenv("ECO_WHISPER_DIR") or None)


def transcribir(datos):
    """Transcripción de una nota de voz (cualquier formato que entienda ffmpeg), hasta 2 minutos."""
    with tempfile.TemporaryDirectory() as tmp:
        entrada = os.path.join(tmp, "entrada")
        wav = os.path.join(tmp, "audio.wav")
        with open(entrada, "wb") as f:
            f.write(datos)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", entrada, "-t", "120", "-ac", "1", "-ar", "16000", wav],
                       check=True, timeout=60)
        segmentos, info = _whisper().transcribe(wav, beam_size=1, vad_filter=True)
        texto = " ".join(s.text.strip() for s in segmentos).strip()
    return {"texto": texto, "idioma": info.language, "segundos": round(info.duration, 1)}
