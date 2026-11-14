"""
Archivos de ejemplo para el verificador de procedencia (todos sintéticos; firmantes ficticios de la CA de demostración).

  imagen_stable_diffusion.png  PNG con el bloque de texto "parameters" que escriben Stable Diffusion / A1111
  imagen_ia_iptc.jpg           JPEG con XMP IPTC DigitalSourceType = trainedAlgorithmicMedia (sin C2PA)
  video_firmado_medio.mp4      video firmado con C2PA por "El Faro Regional" (captura digital)
  video_generado_ia.mp4        video firmado con C2PA por "Estudio Demo IA" que declara trainedAlgorithmicMedia

Requiere ffmpeg para los videos. Uso: python -m corpus.generar_ejemplos
"""

import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, PngImagePlugin

sys.path.insert(0, str(Path(__file__).resolve().parent))
from procedencia_corpus import FUENTE, firmante  # noqa: E402

DESTINO = Path(__file__).resolve().parent / "ejemplos"
XMP_IA = ('<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
          '<rdf:Description xmlns:Iptc4xmpExt="http://iptc.org/std/Iptc4xmpExt/2008-02-29/" '
          'Iptc4xmpExt:DigitalSourceType="http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"/>'
          '</rdf:RDF></x:xmpmeta>')


def imagen(texto, color):
    img = Image.new("RGB", (640, 360), color)
    d = ImageDraw.Draw(img)
    d.rectangle([40, 120, 600, 240], fill=(250, 250, 250))
    d.text((60, 170), texto, fill=(20, 20, 20))
    return img


def firmar_archivo(origen, destino, medio, formato, ia):
    import c2pa
    cadena, clave = firmante(medio)
    manifiesto = {
        "claim_generator_info": [{"name": "Generador de video sintetico (demo ECO)" if ia else "ECO laboratorio",
                                  "version": "1.0"}],
        "title": destino.name, "format": formato,
        "assertions": [{"label": "c2pa.actions", "data": {"actions": [{
            "action": "c2pa.created", "digitalSourceType": FUENTE + ("trainedAlgorithmicMedia" if ia else "digitalCapture")}]}},
            {"label": "org.eco.publicacion", "data": {"medio": medio, "fecha": "2026-11-14T09:00:00-05:00"}}],
    }
    info = c2pa.C2paSignerInfo(c2pa.C2paSigningAlg.ES256, cadena, clave, None)
    with c2pa.Signer.from_info(info) as signer, c2pa.Builder(json.dumps(manifiesto)) as b:
        b.sign_file(origen, destino, signer)


def video(ruta, color, texto):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    f"color=c={color}:s=480x270:d=3,drawbox=x=40:y=100:w=400:h=70:color=white@0.9:t=fill",
                    "-vf", "format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
                    "-metadata", f"comment={texto}", "-movflags", "+faststart", str(ruta)], check=True)


def main():
    DESTINO.mkdir(parents=True, exist_ok=True)
    meta = PngImagePlugin.PngInfo()
    meta.add_text("parameters", "a flooded street at night, photorealistic, news photo\n"
                  "Negative prompt: blurry\nSteps: 30, Sampler: DPM++ 2M Karras, CFG scale: 7, Seed: 1234, "
                  "Model: sd_xl_base_1.0 (ejemplo sintetico de ECO)")
    imagen("Ejemplo sintetico: imagen con parametros de Stable Diffusion", (70, 110, 160)).save(
        DESTINO / "imagen_stable_diffusion.png", "PNG", pnginfo=meta)
    imagen("Ejemplo sintetico: marca IPTC de IA en XMP", (150, 90, 120)).save(
        DESTINO / "imagen_ia_iptc.jpg", "JPEG", quality=88, xmp=XMP_IA.encode())
    with tempfile.TemporaryDirectory() as tmp:
        for nombre, color, medio, ia in (("video_firmado_medio.mp4", "0x2a6f97", "El Faro Regional", False),
                                         ("video_generado_ia.mp4", "0x7a3e9d", "Estudio Demo IA", True)):
            base = Path(tmp) / nombre
            video(base, color, "Ejemplo sintetico del laboratorio ECO")
            firmar_archivo(base, DESTINO / nombre, medio, "video/mp4", ia)
    for f in sorted(DESTINO.iterdir()):
        print(f"{f.name}: {f.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
