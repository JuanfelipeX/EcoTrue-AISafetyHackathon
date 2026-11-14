"""
Filtros forenses de visión por computadora para imágenes (experimental, complementario a C2PA y metadatos).

  - ELA (Error Level Analysis): se recomprime la imagen y se mira la diferencia. Zonas editadas o pegadas suelen
    responder distinto a la recompresión.
  - Residuo de ruido: imagen menos su versión suavizada (filtro de mediana). Una cámara deja un ruido de sensor
    parejo; muchas imágenes generadas lo tienen demasiado liso o desigual por zonas.
  - Espectro del residuo (FFT): el escalado interno de muchos generadores deja picos periódicos en frecuencia.

Devuelve los tres mapas como imágenes (para que la persona vea) y unos indicadores con su lectura.
ADVERTENCIA: no está evaluado. Los generadores recientes pasan estos filtros y la compresión de redes sociales
también deja rasgos atípicos. Es un indicio para mirar con más cuidado, nunca una prueba.
"""

import base64
import io

LADO_MAX = 1024


def _png_b64(img, lado=384):
    from PIL import Image
    img = img.copy()
    img.thumbnail((lado, lado), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _normalizar(arr):
    import numpy as np
    from PIL import Image
    a = arr.astype("float64")
    lo, hi = np.percentile(a, 1), np.percentile(a, 99.5)
    a = np.clip((a - lo) / max(hi - lo, 1e-9), 0, 1) * 255
    return Image.fromarray(a.astype("uint8"))


def analizar(datos):
    import numpy as np
    from PIL import Image, ImageChops, ImageFilter

    img = Image.open(io.BytesIO(datos)).convert("RGB")
    img.thumbnail((LADO_MAX, LADO_MAX), Image.Resampling.LANCZOS)
    w, h = img.size
    if w < 64 or h < 64:
        raise ValueError("Imagen demasiado pequeña para los filtros forenses.")

    # 1) ELA
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    recomprimida = Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
    ela = np.asarray(ImageChops.difference(img, recomprimida), dtype="float64").mean(axis=2)
    bloques = [ela[y:y + 32, x:x + 32].mean() for y in range(0, h - 31, 32) for x in range(0, w - 31, 32)]
    ela_cv = float(np.std(bloques) / (np.mean(bloques) + 1e-9)) if bloques else 0.0

    # 2) Residuo de ruido
    gris = img.convert("L")
    suave = gris.filter(ImageFilter.MedianFilter(3))
    residuo = np.asarray(gris, dtype="float64") - np.asarray(suave, dtype="float64")
    nivel = float(np.std(residuo))
    std_bloques = [residuo[y:y + 32, x:x + 32].std() for y in range(0, h - 31, 32) for x in range(0, w - 31, 32)]
    ruido_cv = float(np.std(std_bloques) / (np.mean(std_bloques) + 1e-9)) if std_bloques else 0.0

    # 3) Espectro del residuo: picos periódicos fuera del centro
    n = min(h, w, 512)
    trozo = residuo[(h - n) // 2:(h - n) // 2 + n, (w - n) // 2:(w - n) // 2 + n]
    ventana = np.outer(np.hanning(n), np.hanning(n))
    espectro = np.log1p(np.abs(np.fft.fftshift(np.fft.fft2(trozo * ventana))))
    yy, xx = np.mgrid[0:n, 0:n]
    radio = np.hypot(yy - n / 2, xx - n / 2)
    anillo = espectro[(radio > n * 0.08) & (radio < n * 0.48)]
    pico = float((anillo.max() - np.median(anillo)) / (anillo.std() + 1e-9)) if anillo.size else 0.0

    indicadores = [
        {"nombre": "Ruido de sensor", "valor": round(nivel, 2),
         "atipico": nivel < 1.2,
         "lectura": "muy bajo: imagen demasiado lisa, típico de generadores o de mucho filtrado" if nivel < 1.2
         else "presente, como el de una cámara o una imagen comprimida"},
        {"nombre": "Uniformidad del ruido", "valor": round(ruido_cv, 2),
         "atipico": ruido_cv > 1.8,
         "lectura": "muy desigual por zonas (zonas lisas junto a zonas con textura)" if ruido_cv > 1.8
         else "bastante parejo en toda la imagen"},
        {"nombre": "Nivel de error (ELA)", "valor": round(ela_cv, 2),
         "atipico": ela_cv > 1.3,
         "lectura": "algunas zonas responden muy distinto a la recompresión (posible edición o pegado)" if ela_cv > 1.3
         else "respuesta pareja a la recompresión"},
        {"nombre": "Picos periódicos en frecuencia", "valor": round(pico, 1),
         "atipico": pico > 9,
         "lectura": "hay picos periódicos marcados, como los que deja el escalado de algunos generadores" if pico > 9
         else "sin picos periódicos llamativos"},
    ]
    atipicos = sum(i["atipico"] for i in indicadores)
    nivel_txt = {0: "ninguno", 1: "pocos", 2: "algunos"}.get(atipicos, "varios")
    return {
        "rasgos_atipicos": atipicos,
        "lectura": f"{atipicos} de 4 rasgos atípicos ({nivel_txt}). "
                   + ("Vale la pena mirar con más cuidado y buscar el origen de la imagen." if atipicos >= 2
                      else "Nada llamativo en estos filtros, lo que no prueba que la imagen sea auténtica."),
        "indicadores": indicadores,
        "mapas": {"ela": _png_b64(_normalizar(ela)), "residuo": _png_b64(_normalizar(np.abs(residuo))),
                  "espectro": _png_b64(_normalizar(espectro))},
        "aviso": ("Experimental y no evaluado. Los generadores recientes pasan estos filtros y la compresión de redes "
                  "sociales también deja rasgos atípicos: es un indicio para mirar con cuidado, nunca una prueba."),
    }
