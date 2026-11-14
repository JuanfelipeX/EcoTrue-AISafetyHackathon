"""
Compara tres métodos sobre el corpus sintético:
  linea_base  similitud de texto + enlaces
  hechos      ECO por hechos atómicos
  hibrido     ECO por hechos + guardia contra copias casi idénticas con datos agregados

Una sola extracción de hechos por escenario (llamada al LLM) alimenta a hechos e híbrido.

Uso (desde la carpeta eco):
  python -m evaluacion.evaluar                                       modelo del .env
  python -m evaluacion.evaluar --modelo openai/gpt-5-mini
  python -m evaluacion.evaluar --modelo manual/claude-opus-5-5-sesion

Guarda el detalle en evaluacion/resultados/comparacion_<modelo>.json
"""

import argparse
import json
import re

from motor import hechos as metodo_hechos
from motor import linea_base
from motor.config import config
from motor.llm import ClienteLLM, ErrorLLM, PendienteManual
from evaluacion.evaluar_linea_base import DIR_RESULTADOS, TIPOS, cargar_escenarios, evaluar_escenario, pct, resumir

METODOS = ["linea_base", "hechos", "hibrido"]
NOMBRES = {"linea_base": "Línea base", "hechos": "ECO hechos", "hibrido": "ECO híbrido"}


def tabla_comparativa(resumenes):
    print(f"\nExactitud del conteo de fuentes independientes por tipo de escenario")
    print(f"{'tipo':<22}{'n':>3}" + "".join(f"{NOMBRES[m]:>14}" for m in METODOS))
    for t in TIPOS:
        if t not in resumenes["linea_base"]:
            continue
        n = resumenes["linea_base"][t]["n"]
        print(f"{t:<22}{n:>3}" + "".join(f"{pct(resumenes[m][t]['exactitud']):>14}" for m in METODOS))
    for conjunto, tipos in (("principal", TIPOS[:4]), ("estrés", TIPOS[4:])):
        fila = f"{'global ' + conjunto:<22}{'':>3}"
        for m in METODOS:
            sub = [resumenes[m][t] for t in tipos if t in resumenes[m]]
            total = sum(r["n"] for r in sub)
            fila += f"{pct(sum(r['exactitud'] * r['n'] for r in sub) / total) if total else '—':>14}"
        print(fila)
    org = {m: resumenes[m]["organico"]["fusion_falsa"] for m in METODOS if "organico" in resumenes[m]}
    print(f"\nFusión falsa en cobertura orgánica (falsos positivos): "
          + ", ".join(f"{NOMBRES[m]} {pct(v).strip()}" for m, v in org.items()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--modelo", default=config.llm_modelo)
    parser.add_argument("--umbral", type=float, default=config.umbral_similitud,
                        help="umbral de similitud de la línea base y de la guardia del híbrido")
    parser.add_argument("--min-novedad", type=int, default=1)
    parser.add_argument("--conjunto", choices=["desarrollo", "prueba"], default="desarrollo",
                        help="desarrollo = principal + estrés (usado para diseñar ECO); prueba = eventos retenidos e07-e09")
    args = parser.parse_args()

    cliente = ClienteLLM(modelo=args.modelo, respaldo=[])
    escenarios = cargar_escenarios()
    if args.conjunto == "prueba":
        escenarios = [(e, d) for e, d in escenarios if e.get("conjunto") == "prueba"]
    else:
        escenarios = [(e, d) for e, d in escenarios if e.get("conjunto") in ("principal", "estres", None)]
    print(f"Conjunto: {args.conjunto} ({len(escenarios)} mundos) · modelo: {args.modelo}")

    filas = {m: [] for m in METODOS}
    detalle, pendientes, fallos = [], 0, []
    for esc, docs in escenarios:
        filas["linea_base"].append(evaluar_escenario(esc, linea_base.analizar(docs, args.umbral)))
        try:
            extraidos, respuesta = metodo_hechos.extraer_hechos(esc["afirmacion"], docs, cliente)
        except PendienteManual:
            pendientes += 1
            continue
        except ErrorLLM as e:
            fallos.append(f"{esc['id']}: {e}")
            continue
        res_h = metodo_hechos.analizar(docs, esc["afirmacion"], hechos=extraidos, min_novedad=args.min_novedad)
        res_x = metodo_hechos.analizar(docs, esc["afirmacion"], hechos=extraidos, min_novedad=args.min_novedad,
                                       umbral_copia=args.umbral)
        f_h, f_x = evaluar_escenario(esc, res_h), evaluar_escenario(esc, res_x)
        filas["hechos"].append(f_h)
        filas["hibrido"].append(f_x)
        detalle.append({"escenario": esc["id"], "tipo": esc["tipo"],
                        "evaluacion": {"hechos": f_h, "hibrido": f_x}, "resultado_hibrido": res_x})

    if pendientes:
        print(f"{pendientes} escenarios quedaron pendientes de respuesta manual en .cache/pendientes/.")
        print("Responda y ejecute: python -m scripts.importar_respuestas ; luego repita esta evaluación.")
        return
    if fallos:
        print("Escenarios con error del LLM (se excluyen de la comparación):\n  " + "\n  ".join(fallos))
        if not filas["hechos"]:
            return
        evaluados = {f["escenario"] for f in filas["hechos"]}
        filas["linea_base"] = [f for f in filas["linea_base"] if f["escenario"] in evaluados]

    resumenes = {m: resumir(filas[m]) for m in METODOS}
    tabla_comparativa(resumenes)

    DIR_RESULTADOS.mkdir(exist_ok=True)
    nombre = re.sub(r"[^a-zA-Z0-9_.-]", "_", args.modelo)
    sufijo = "__prueba" if args.conjunto == "prueba" else ""
    ruta = DIR_RESULTADOS / f"comparacion_{nombre}{sufijo}.json"
    ruta.write_text(json.dumps({
        "modelo": args.modelo, "conjunto": args.conjunto, "umbral": args.umbral, "min_novedad": args.min_novedad,
        "resumenes": resumenes, "errores": fallos, "detalle": detalle,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\nDetalle guardado en {ruta}")


if __name__ == "__main__":
    main()
