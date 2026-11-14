"""
¿Voz clonada? Análisis de un audio en dos capas.

1. Procedencia (C2PA): si el archivo trae credenciales de contenido válidas, dicen quién lo creó y si se declaró
   generado por IA. Es la respuesta más fuerte, pero casi ningún audio real las trae y WhatsApp las borra.
2. Detector AASIST-L (clovaai/aasist, MIT): si no hay firma, estima si la voz es sintética. Se usa la versión
   reentrenada por ECO con aumento de códec Opus (deteccion_voz/experimento.py) cuando está disponible;
   si no, la preentrenada en ASVspoof 2019.

El detector se equivoca: ver deteccion_voz/aasist/calibracion.json (EER en In-the-Wild, en inglés). Un resultado
"parece sintética" es una alerta para verificar por otro canal, no una prueba.
"""

import json
import shutil
import subprocess
from functools import lru_cache

from .config import RAIZ_PROYECTO

DIR_AASIST = RAIZ_PROYECTO / "deteccion_voz" / "aasist"
LARGO = 64600            # ~4 s a 16 kHz
MAX_SEGUNDOS = 30
MAX_BYTES_AUDIO = 10 * 1024 * 1024
TIPOS_AUDIO = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".mp4": "video/mp4",
               ".flac": "audio/flac", ".ogg": None, ".opus": None, ".webm": None}


@lru_cache(maxsize=1)
def calibracion():
    ruta = DIR_AASIST / "calibracion.json"
    if ruta.exists():
        return json.loads(ruta.read_text(encoding="utf-8"))
    return {"pesos": "AASIST-L.pth", "umbral": 0.0, "banda": 1.0, "nota": "Sin calibrar: modelo preentrenado en ASVspoof 2019."}


@lru_cache(maxsize=1)
def _modelo():
    import importlib.util
    import torch
    spec = importlib.util.spec_from_file_location("aasist_modelo", DIR_AASIST / "AASIST.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    conf = json.loads((DIR_AASIST / "AASIST-L.conf").read_text(encoding="utf-8"))
    m = modulo.Model(conf["model_config"])
    pesos = DIR_AASIST / calibracion()["pesos"]
    if not pesos.exists():
        pesos = DIR_AASIST / "AASIST-L.pth"
    m.load_state_dict(torch.load(pesos, map_location="cpu", weights_only=True))
    m.eval()
    torch.set_num_threads(2)
    return m, pesos.name


def disponible():
    import importlib.util
    return bool(importlib.util.find_spec("torch")) and bool(shutil.which("ffmpeg"))


def decodificar(datos):
    """Cualquier formato que entienda ffmpeg → float32 mono 16 kHz (máximo 30 s)."""
    import numpy as np
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", "pipe:0", "-t", str(MAX_SEGUNDOS), "-ac", "1", "-ar", "16000",
                        "-f", "s16le", "pipe:1"], input=datos, capture_output=True, timeout=60)
    if r.returncode != 0 or not r.stdout:
        raise ValueError("No se pudo leer el audio: " + r.stderr.decode(errors="replace")[:200])
    return np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def detectar(muestras):
    import numpy as np
    import torch
    if len(muestras) < 16000:
        raise ValueError("El audio es demasiado corto (menos de 1 segundo).")
    ventanas = []
    for inicio in range(0, len(muestras), LARGO):
        trozo = muestras[inicio:inicio + LARGO]
        if len(trozo) < 16000 and ventanas:
            break
        if len(trozo) < LARGO:
            trozo = np.tile(trozo, LARGO // len(trozo) + 1)[:LARGO]
        ventanas.append(trozo)
    m, nombre_pesos = _modelo()
    with torch.no_grad():
        _, out = m(torch.from_numpy(np.stack(ventanas)))
    margenes = (out[:, 1] - out[:, 0]).numpy().tolist()  # > umbral: más parecido a voz real
    cal = calibracion()
    mediana = float(np.median(margenes))
    if mediana < cal["umbral"] - cal["banda"]:
        veredicto, texto = "sintetica", "Parece voz sintética (clonada o generada)."
    elif mediana > cal["umbral"] + cal["banda"]:
        veredicto, texto = "real", "Parece voz real."
    else:
        veredicto, texto = "incierto", "No concluyente: el puntaje está cerca del umbral."
    if not cal.get("confiable", True):
        veredicto = "no_confiable"
        texto = ("Detector sin validar para audio real: en la prueba se equivocó como el azar "
                 f"({cal['eer']['limpio']:.0%} de error). No uses este resultado para decidir; verifica por otro canal.")
    return {"modelo": f"AASIST-L ({nombre_pesos})", "segundos_analizados": round(len(muestras) / 16000, 1),
            "ventanas": len(ventanas), "margenes": [round(x, 3) for x in margenes], "puntaje": round(mediana, 3),
            "umbral": cal["umbral"], "veredicto": veredicto, "explicacion": texto,
            "error_de_referencia": cal.get("eer"), "nota_calibracion": cal.get("nota")}


def analizar_audio(datos, nombre="audio"):
    from . import procedencia
    if len(datos) > MAX_BYTES_AUDIO:
        raise ValueError("El audio supera 10 MB.")
    sufijo = "." + nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
    resultado = {"nombre": nombre, "bytes": len(datos)}
    mime = TIPOS_AUDIO.get(sufijo)
    if mime:
        c2pa = procedencia.verificar(datos, mime)
        c2pa.pop("huella", None)
    else:
        c2pa = {"estado": "ausente", "codigos": ["formato sin soporte C2PA (ogg/opus/webm, como las notas de voz)"]}
    resultado["procedencia"] = c2pa
    if not disponible():
        resultado["detector"] = {"veredicto": "no_disponible",
                                 "explicacion": "El detector requiere PyTorch y ffmpeg (instale requirements-voz.txt)."}
    else:
        resultado["detector"] = detectar(decodificar(datos))
    if c2pa.get("estado") == "confiable":
        resultado["conclusion"] = ("Tiene credenciales de contenido confiables" +
                                   (" y se declara generado por IA." if c2pa.get("generada_por_ia") else ".") +
                                   " La firma pesa más que el detector.")
    else:
        resultado["conclusion"] = resultado["detector"].get("explicacion", "")
    resultado["aviso"] = ("El detector se equivoca, sobre todo con audio comprimido o en otros idiomas. Úselo como alerta "
                          "para verificar por otro canal (llamar de vuelta, preguntar algo que solo esa persona sabe), "
                          "no como prueba.")
    return resultado
