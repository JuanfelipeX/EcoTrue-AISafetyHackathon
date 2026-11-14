"""
Extrae solo los audios necesarios de In-the-Wild sin descargar el ZIP completo (8,2 GB):
lee el índice del ZIP por rangos HTTP y de cada audio solo los primeros bytes (~4 s a 16 kHz bastan para AASIST).

Uso: python zip_remoto.py --destino /opt/voz/itw_parcial --por-clase-prueba 600 --por-clase-entreno 1000
Deja meta.csv y los .wav elegidos en <destino>/release_in_the_wild/ (misma partición por hablante que experimento.py).
"""

import argparse
import csv
import io
import random
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

URL = "https://huggingface.co/datasets/mueller91/In-The-Wild/resolve/main/release_in_the_wild.zip"
PREFIJO_BYTES = 400_000  # ~4 s de WAV a 44,1 kHz mono 16 bits; sobra a 16 kHz


class ArchivoHTTP(io.RawIOBase):
    def __init__(self, url):
        self.url = url
        cab = urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30)
        self.url = cab.geturl()  # tras la redirección al CDN
        self.largo = int(cab.headers["Content-Length"])
        self.pos = 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def seek(self, offset, whence=0):
        self.pos = offset if whence == 0 else self.pos + offset if whence == 1 else self.largo + offset
        return self.pos

    def tell(self):
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.largo - self.pos
        if n == 0 or self.pos >= self.largo:
            return b""
        fin = min(self.pos + n, self.largo) - 1
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{fin}"})
        datos = urllib.request.urlopen(req, timeout=60).read()
        self.pos += len(datos)
        return datos

    def readinto(self, b):
        datos = self.read(len(b))
        b[:len(datos)] = datos
        return len(datos)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--destino", default="/opt/voz/itw_parcial")
    ap.add_argument("--por-clase-prueba", type=int, default=600)
    ap.add_argument("--por-clase-entreno", type=int, default=1000)
    ap.add_argument("--semilla", type=int, default=7)
    ap.add_argument("--hilos", type=int, default=48)
    a = ap.parse_args()
    destino = Path(a.destino) / "release_in_the_wild"
    destino.mkdir(parents=True, exist_ok=True)

    z = zipfile.ZipFile(io.BufferedReader(ArchivoHTTP(URL), buffer_size=1 << 20))
    nombres = {Path(n).name: n for n in z.namelist()}
    meta = z.read(nombres["meta.csv"]).decode("utf-8")
    (destino / "meta.csv").write_text(meta, encoding="utf-8")
    filas = list(csv.DictReader(io.StringIO(meta)))
    print(f"meta.csv: {len(filas)} audios", flush=True)

    # Misma selección que experimento.py (misma semilla y mismo orden de llamadas al generador).
    hablantes = sorted({f["speaker"] for f in filas})
    rng = random.Random(a.semilla)
    rng.shuffle(hablantes)
    corte = int(len(hablantes) * 0.7)
    h_e, h_p = set(hablantes[:corte]), set(hablantes[corte:])

    def muestra(hs, n):
        reales = [f for f in filas if f["speaker"] in hs and f["label"].strip().lower().startswith("bona")]
        falsos = [f for f in filas if f["speaker"] in hs and not f["label"].strip().lower().startswith("bona")]
        rng.shuffle(reales)
        rng.shuffle(falsos)
        return [f["file"] for f in reales[:n] + falsos[:n]]

    elegidos = muestra(h_p, a.por_clase_prueba) + muestra(h_e, a.por_clase_entreno)
    url_cdn = ArchivoHTTP(URL).url
    infos = {Path(i.filename).name: i for i in z.infolist()}

    def bajar(nombre):
        info = infos[nombre]
        if (destino / nombre).exists():
            return
        # Una sola petición: cabecera local (30 bytes + nombre + extra) y el inicio de los datos.
        req = urllib.request.Request(url_cdn, headers={
            "Range": f"bytes={info.header_offset}-{info.header_offset + 30 + 512 + PREFIJO_BYTES}"})
        bloque = urllib.request.urlopen(req, timeout=60).read()
        n_nombre, n_extra = int.from_bytes(bloque[26:28], "little"), int.from_bytes(bloque[28:30], "little")
        inicio = 30 + n_nombre + n_extra
        if info.compress_type == zipfile.ZIP_STORED:
            (destino / nombre).write_bytes(bloque[inicio:inicio + min(info.compress_size, PREFIJO_BYTES)])
        else:
            (destino / nombre).write_bytes(z.read(info.filename))

    with ThreadPoolExecutor(a.hilos) as ex:
        for i, _ in enumerate(ex.map(bajar, elegidos), start=1):
            if i % 400 == 0:
                print(f"  {i}/{len(elegidos)}", flush=True)
    print(f"Listo: {len(elegidos)} audios en {destino}", flush=True)


if __name__ == "__main__":
    main()
