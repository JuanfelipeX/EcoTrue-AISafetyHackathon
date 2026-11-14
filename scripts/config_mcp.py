"""
Conecta el servidor MCP de ECO con Claude Desktop y Claude Code, con las rutas reales de este computador.

Uso (desde la carpeta eco, con el entorno virtual activo):
  python -m scripts.config_mcp              imprime la configuración y los comandos
  python -m scripts.config_mcp --instalar   además la escribe en Claude Desktop y la registra en Claude Code

Luego reinicie Claude Desktop. Prueba sin cliente: python -m scripts.probar_mcp
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from motor.config import RAIZ_PROYECTO


def rutas_claude_desktop():
    """Posibles ubicaciones de claude_desktop_config.json (instalador clásico, Microsoft Store, macOS)."""
    rutas = []
    appdata, local = os.getenv("APPDATA"), os.getenv("LOCALAPPDATA")
    if local:
        for paquete in Path(local, "Packages").glob("Claude_*"):
            rutas.append(paquete / "LocalCache" / "Roaming" / "Claude" / "claude_desktop_config.json")
    if appdata:
        rutas.append(Path(appdata) / "Claude" / "claude_desktop_config.json")
    rutas.append(Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json")
    return rutas


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instalar", action="store_true")
    args = parser.parse_args()

    python = sys.executable
    servidor = str(RAIZ_PROYECTO / "mcp_eco" / "servidor.py")
    entrada = {"command": python, "args": [servidor], "env": {"PYTHONIOENCODING": "utf-8"}}

    print("1) Claude Desktop: agregue esto a claude_desktop_config.json y reinicie la aplicación:\n")
    print(json.dumps({"mcpServers": {"eco": entrada}}, indent=2, ensure_ascii=False))
    print("\n2) Claude Code:\n")
    print(f'   claude mcp add eco --scope user -e PYTHONIOENCODING=utf-8 -- "{python}" "{servidor}"')
    print("\nEl servidor lee el .env de la carpeta del proyecto, así que usa los mismos modelos y claves.")

    if not args.instalar:
        return
    print()
    for ruta in rutas_claude_desktop():
        if not ruta.parent.parent.exists():
            continue
        ruta.parent.mkdir(parents=True, exist_ok=True)
        datos = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() and ruta.read_text(encoding="utf-8").strip() else {}
        datos.setdefault("mcpServers", {})["eco"] = entrada
        ruta.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Claude Desktop configurado: {ruta}")
    claude = shutil.which("claude")
    if claude:
        subprocess.run([claude, "mcp", "remove", "eco", "-s", "user"], capture_output=True)
        r = subprocess.run([claude, "mcp", "add", "eco", "--scope", "user", "-e", "PYTHONIOENCODING=utf-8", "--",
                            python, servidor], capture_output=True, text=True)
        print("Claude Code:", (r.stdout or r.stderr).strip().splitlines()[0] if (r.stdout or r.stderr) else "listo")
    else:
        print("No encontré el comando claude; registre Claude Code con el comando de arriba.")


if __name__ == "__main__":
    main()
