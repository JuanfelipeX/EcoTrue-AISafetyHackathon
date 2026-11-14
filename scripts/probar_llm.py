"""
Prueba rápida de los proveedores LLM configurados en .env.

Uso (desde la carpeta eco):
  python -m scripts.probar_llm                      prueba el principal y los de respaldo, uno por uno
  python -m scripts.probar_llm --modelo openai/gpt-5-mini
"""

import argparse

from motor.config import config
from motor.llm import ClienteLLM, ErrorLLM

PROMPT = ('Extrae los hechos de esta frase como JSON con la forma {"hechos": ["..."]}: '
          '"El puente La Concordia fue cerrado; pasan 9.000 vehículos al día."')


def probar(especificacion):
    cliente = ClienteLLM(usar_cache=False)
    try:
        datos, r = cliente.completar_json(PROMPT, modelo=especificacion)
        print(f"OK   {especificacion:<50} {r.segundos:>5}s  tokens {r.tokens_entrada}/{r.tokens_salida}  -> {datos}")
    except ErrorLLM as e:
        print(f"FALLA {especificacion}\n      {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--modelo", help="proveedor/modelo a probar")
    args = parser.parse_args()
    modelos = [args.modelo] if args.modelo else [config.llm_modelo] + config.llm_modelos_respaldo
    for m in modelos:
        probar(m)


if __name__ == "__main__":
    main()
