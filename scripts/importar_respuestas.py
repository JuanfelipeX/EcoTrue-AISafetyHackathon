"""
Importa respuestas dadas a mano para el proveedor "manual".

Flujo:
  1. Correr el pipeline con un modelo manual/<nombre>. Los prompts sin respuesta quedan en
     .cache/pendientes/<hash>.json
  2. Escribir cada respuesta (texto tal cual lo daría el modelo) en .cache/respuestas/<hash>.txt
  3. python -m scripts.importar_respuestas
     Pasa cada respuesta a la caché del LLM y borra el pendiente.
  4. Volver a correr el pipeline: ahora encuentra las respuestas en caché.

  python -m scripts.importar_respuestas --listar     muestra los pendientes sin importar nada
"""

import argparse
import json

from motor.config import config
from motor.llm import RespuestaLLM
from dataclasses import asdict

DIR_PENDIENTES = config.dir_cache.parent / "pendientes"
DIR_RESPUESTAS = config.dir_cache.parent / "respuestas"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--listar", action="store_true")
    args = parser.parse_args()

    pendientes = sorted(DIR_PENDIENTES.glob("*.json")) if DIR_PENDIENTES.exists() else []
    if args.listar:
        for p in pendientes:
            datos = json.loads(p.read_text(encoding="utf-8"))
            print(f"{p.stem}  {datos['modelo']}  ({len(datos['prompt'])} caracteres)")
        print(f"Pendientes: {len(pendientes)}")
        return

    importadas = 0
    for p in pendientes:
        respuesta = DIR_RESPUESTAS / f"{p.stem}.txt"
        if not respuesta.exists():
            continue
        datos = json.loads(p.read_text(encoding="utf-8"))
        r = RespuestaLLM(texto=respuesta.read_text(encoding="utf-8"), modelo=datos["modelo"], proveedor="manual")
        config.dir_cache.mkdir(parents=True, exist_ok=True)
        (config.dir_cache / p.name).write_text(json.dumps(asdict(r), ensure_ascii=False), encoding="utf-8")
        p.unlink()
        importadas += 1
    restantes = len(list(DIR_PENDIENTES.glob("*.json"))) if DIR_PENDIENTES.exists() else 0
    print(f"Importadas: {importadas} | Pendientes sin respuesta: {restantes}")


if __name__ == "__main__":
    main()
