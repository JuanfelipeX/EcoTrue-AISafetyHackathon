"""
Evalúa la línea base sobre el corpus sintético y compara con la respuesta correcta.

Uso (desde la carpeta eco):
  python -m evaluacion.evaluar_linea_base               umbral del .env
  python -m evaluacion.evaluar_linea_base --umbral 0.6
  python -m evaluacion.evaluar_linea_base --barrido     prueba umbrales de 0.3 a 0.9

Métricas por tipo de escenario:
  exactitud      % de escenarios donde el conteo de fuentes efectivas es exacto
  error_medio    diferencia absoluta promedio entre conteo estimado y real
  colapso        (solo cascadas) % donde todo se reconoció como un solo origen
  origen_ok      (solo cascadas) % donde se identificó bien la página de origen
  fusion_falsa   (solo orgánico) % donde se juntaron medios que eran independientes
"""

import argparse
import json
from pathlib import Path

from motor import linea_base
from motor.config import RAIZ_PROYECTO, config
from motor.extraccion import cargar_desde_archivo

DIR_CORPUS = RAIZ_PROYECTO / "corpus"
DIR_RESULTADOS = Path(__file__).resolve().parent / "resultados"
TIPOS = ["organico", "literal", "parafrasis", "comunicado", "fabricado_literal", "fabricado_parafrasis"]


def cargar_escenarios():
    gt = json.loads((DIR_CORPUS / "ground_truth.json").read_text(encoding="utf-8"))
    escenarios = []
    for esc in gt["escenarios"]:
        docs = [cargar_desde_archivo(DIR_CORPUS / "sitios" / esc["id"] / f"{p['id']}.html", p["url"], p["id"])
                for p in esc["paginas"]]
        escenarios.append((esc, docs))
    return escenarios


def evaluar_escenario(esc, resultado):
    pred = resultado["fuentes_efectivas"]
    esperado = esc["fuentes_efectivas_esperadas"]
    fila = {"escenario": esc["id"], "tipo": esc["tipo"], "aparentes": esc["fuentes_aparentes"],
            "esperado": esperado, "estimado": pred, "exacto": pred == esperado, "error": abs(pred - esperado)}
    if esc["tipo"] == "organico":
        fila["fusion_falsa"] = pred < esperado
    else:
        fila["colapso"] = pred == 1
        grupo = next((g for g in resultado["grupos"] if esc["origen"] in g["miembros"]), None)
        fila["origen_ok"] = bool(grupo and grupo["origen"] == esc["origen"])
    return fila


def resumir(filas):
    resumen = {}
    for t in TIPOS:
        sub = [f for f in filas if f["tipo"] == t]
        if not sub:
            continue
        r = {"n": len(sub),
             "exactitud": sum(f["exacto"] for f in sub) / len(sub),
             "error_medio": sum(f["error"] for f in sub) / len(sub)}
        if t == "organico":
            r["fusion_falsa"] = sum(f["fusion_falsa"] for f in sub) / len(sub)
        else:
            r["colapso"] = sum(f["colapso"] for f in sub) / len(sub)
            r["origen_ok"] = sum(f["origen_ok"] for f in sub) / len(sub)
        resumen[t] = r
    return resumen


def correr(escenarios, umbral):
    filas = [evaluar_escenario(esc, linea_base.analizar(docs, umbral)) for esc, docs in escenarios]
    return filas, resumir(filas)


def pct(x):
    return f"{x * 100:5.0f}%"


def imprimir_resumen(resumen, umbral):
    print(f"\nLínea base (similitud de texto + enlaces), umbral = {umbral}")
    print(f"{'tipo':<22}{'n':>3}{'exactitud':>11}{'error medio':>13}{'colapso':>9}{'origen ok':>11}{'fusión falsa':>14}")
    for t, r in resumen.items():
        print(f"{t:<22}{r['n']:>3}{pct(r['exactitud']):>11}{r['error_medio']:>13.2f}"
              f"{pct(r['colapso']) if 'colapso' in r else '—':>9}"
              f"{pct(r['origen_ok']) if 'origen_ok' in r else '—':>11}"
              f"{pct(r['fusion_falsa']) if 'fusion_falsa' in r else '—':>14}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--umbral", type=float, default=config.umbral_similitud)
    parser.add_argument("--barrido", action="store_true")
    args = parser.parse_args()

    escenarios = cargar_escenarios()
    DIR_RESULTADOS.mkdir(exist_ok=True)

    if args.barrido:
        print("Barrido de umbrales: exactitud del conteo por tipo")
        print(f"{'umbral':<8}" + "".join(f"{t[:20]:>22}" for t in TIPOS))
        tabla = {}
        for umbral in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
            _, resumen = correr(escenarios, umbral)
            tabla[umbral] = resumen
            print(f"{umbral:<8}" + "".join(f"{pct(resumen[t]['exactitud']):>22}" for t in TIPOS if t in resumen))
        (DIR_RESULTADOS / "linea_base_barrido.json").write_text(
            json.dumps(tabla, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nGuardado en {DIR_RESULTADOS / 'linea_base_barrido.json'}")
        return

    filas, resumen = correr(escenarios, args.umbral)
    imprimir_resumen(resumen, args.umbral)
    salida = {"metodo": "linea_base", "umbral": args.umbral, "resumen": resumen, "detalle": filas}
    (DIR_RESULTADOS / "linea_base.json").write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDetalle por escenario en {DIR_RESULTADOS / 'linea_base.json'}")


if __name__ == "__main__":
    main()
