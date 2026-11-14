"""
Lanzador de la demo: arranca el servidor de ECO y abre un Chrome con la extensión ya instalada.

Uso (desde la carpeta eco, con el entorno virtual activo):
  python -m scripts.demo                 servidor en 8765 + navegador de demo
  python -m scripts.demo --puerto 8770   otro puerto (la extensión se ajusta sola)
  python -m scripts.demo --sin-navegador solo el servidor

El navegador es "Chrome for Testing": el Chrome normal ya no permite cargar extensiones
desde la línea de comandos (desde la versión 137). Si no está descargado, se descarga con npx
(~170 MB, una sola vez) en .navegador/. Usa un perfil propio en .navegador/perfil, así que no toca
el Chrome personal. Para el Chrome personal: chrome://extensions → Modo de desarrollador →
Cargar descomprimida → carpeta extension/.
"""

import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from motor.config import RAIZ_PROYECTO

DIR_NAVEGADOR = RAIZ_PROYECTO / ".navegador"
DIR_EXTENSION = RAIZ_PROYECTO / "extension"


def buscar_chrome_testing():
    candidatos = sorted(DIR_NAVEGADOR.glob("chrome/*/chrome-*/chrome.exe")) + \
                 sorted(DIR_NAVEGADOR.glob("chrome/*/chrome-*/chrome")) + \
                 sorted(DIR_NAVEGADOR.glob("chrome/*/chrome-*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"))
    return candidatos[-1] if candidatos else None


def descargar_chrome_testing():
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        print("No encontré npx (Node.js). Instale Node o cargue la extensión a mano en chrome://extensions.")
        return None
    print("Descargando Chrome for Testing (una sola vez)…")
    subprocess.run([npx, "-y", "@puppeteer/browsers", "install", "chrome@stable", "--path", str(DIR_NAVEGADOR)], check=True)
    return buscar_chrome_testing()


def servidor_vivo(puerto):
    try:
        with urllib.request.urlopen(f"http://localhost:{puerto}/api/salud", timeout=2) as r:
            return json.load(r).get("estado") == "ok"
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--puerto", type=int, default=8765)
    parser.add_argument("--sin-navegador", action="store_true")
    args = parser.parse_args()
    base = f"http://localhost:{args.puerto}"

    proceso = None
    if servidor_vivo(args.puerto):
        print(f"El servidor de ECO ya está corriendo en {base}")
    else:
        print(f"Arrancando el servidor de ECO en {base} …")
        proceso = subprocess.Popen([sys.executable, "-m", "uvicorn", "api.servidor:app", "--host", "127.0.0.1",
                                    "--port", str(args.puerto)], cwd=RAIZ_PROYECTO)
        for _ in range(40):
            if servidor_vivo(args.puerto):
                break
            time.sleep(0.5)
        else:
            print("El servidor no respondió. Revise el mensaje de uvicorn arriba (¿puerto ocupado? use --puerto).")
            proceso.terminate()
            return

    if not args.sin_navegador:
        chrome = buscar_chrome_testing() or descargar_chrome_testing()
        if chrome:
            perfil = DIR_NAVEGADOR / "perfil"
            perfil.mkdir(parents=True, exist_ok=True)
            # La extensión detecta sola el servidor en 8765, 8766, 8770 u 8000; otro puerto se fija en el popup.
            if args.puerto not in (8765, 8766, 8770, 8000):
                print(f"Aviso: en el popup de la extensión → «Servidor de ECO» escriba {base}")
            subprocess.Popen([str(chrome), f"--user-data-dir={perfil}", f"--load-extension={DIR_EXTENSION}",
                              "--no-first-run", "--no-default-browser-check",
                              f"{base}/", f"{base}/sitios/e01-s1/e01-s1-p03.html"])
            print("Navegador de demo abierto con la extensión de ECO (clic derecho → «ECO: ¿cuántas fuentes reales…?»).")

    print(f"\nPanel: {base}/   ·   Mini-internet: {base}/internet   ·   API: {base}/docs")
    if proceso:
        print("Ctrl+C para detener el servidor.")
        try:
            proceso.wait()
        except KeyboardInterrupt:
            proceso.terminate()


if __name__ == "__main__":
    main()
