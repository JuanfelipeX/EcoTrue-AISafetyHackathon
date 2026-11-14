"""
Evaluación de la señal de procedencia (C2PA + huella visual) en los 12 mundos con fotos firmadas.

Para cada mundo se extraen los hechos una sola vez y se comparan:
  linea_base              similitud de texto
  eco_sin_procedencia     ECO híbrido tal como estaba
  eco_con_procedencia     ECO híbrido + fecha firmada + foto ajena (motor/procedencia.py)

Métricas: conteo exacto de fuentes independientes, origen correcto (el grupo principal empieza en la página
de origen real) y detección de imágenes generadas por IA y de firmas rotas.

Uso (desde la carpeta eco):
  python -m evaluacion.evaluar_procedencia --modelo claudecode/sonnet
"""

import argparse
import json
from collections import defaultdict

from evaluacion.evaluar_linea_base import DIR_RESULTADOS, cargar_escenarios
from motor import hechos as metodo_hechos
from motor import linea_base, procedencia
from motor.config import config
from motor.llm import ClienteLLM


def _origen_ok(esc, res):
    if not esc.get("origen"):
        return None
    grupo = next((g for g in res["grupos"] if esc["origen"] in g["miembros"]), None)
    return bool(grupo and grupo["origen"] == esc["origen"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--modelo", default=None, help="proveedor/modelo para extraer los hechos")
    args = parser.parse_args()
    cliente = ClienteLLM(modelo=args.modelo) if args.modelo else ClienteLLM()
    umbral = config.umbral_similitud

    filas = []
    for esc, docs in cargar_escenarios():
        if esc.get("conjunto") != "procedencia":
            continue
        hechos, _ = metodo_hechos.extraer_hechos(esc["afirmacion"], docs, cliente)
        proc = procedencia.analizar_documentos(docs)
        resultados = {
            "linea_base": linea_base.analizar(docs),
            "eco_sin_procedencia": metodo_hechos.analizar(docs, esc["afirmacion"], hechos=hechos, umbral_copia=umbral),
            "eco_con_procedencia": metodo_hechos.analizar(docs, esc["afirmacion"], hechos=hechos, umbral_copia=umbral,
                                                          procedencia=proc),
        }
        esperado = esc["fuentes_efectivas_esperadas"]
        fila = {"escenario": esc["id"], "tipo": esc["tipo"], "esperado": esperado, "paginas": esc["fuentes_aparentes"]}
        for nombre, res in resultados.items():
            fila[nombre] = {"estimado": res["fuentes_efectivas"], "exacto": res["fuentes_efectivas"] == esperado,
                            "origen_ok": _origen_ok(esc, res)}
        resumen_proc = resultados["eco_con_procedencia"].get("procedencia") or {}
        fila["senales"] = {k: resumen_proc.get(k) for k in ("firmadas_confiables", "firma_rota", "generadas_por_ia",
                                                             "fechas_imposibles", "por_foto_ajena")}
        filas.append(fila)
        print(f"{esc['id']:<8} {esc['tipo']:<24} esperado {esperado} | base {fila['linea_base']['estimado']} | "
              f"ECO {fila['eco_sin_procedencia']['estimado']} | ECO+C2PA {fila['eco_con_procedencia']['estimado']}"
              f" | origen ok: {fila['eco_sin_procedencia']['origen_ok']} → {fila['eco_con_procedencia']['origen_ok']}")

    resumen = defaultdict(dict)
    for metodo in ("linea_base", "eco_sin_procedencia", "eco_con_procedencia"):
        for tipo in sorted({f["tipo"] for f in filas}):
            sub = [f for f in filas if f["tipo"] == tipo]
            origen = [f[metodo]["origen_ok"] for f in sub if f[metodo]["origen_ok"] is not None]
            resumen[metodo][tipo] = {"n": len(sub), "exactitud": sum(f[metodo]["exacto"] for f in sub) / len(sub),
                                     "origen_ok": sum(origen) / len(origen) if origen else None}
    print("\nExactitud por tipo (y origen correcto):")
    for tipo in sorted({f["tipo"] for f in filas}):
        celdas = [f"{m}: {resumen[m][tipo]['exactitud']:.0%}" + (f" (origen {resumen[m][tipo]['origen_ok']:.0%})"
                  if resumen[m][tipo]["origen_ok"] is not None else "") for m in resumen]
        print(f"  {tipo:<24} " + " · ".join(celdas))

    salida = {"modelo": args.modelo or config.llm_modelo, "conjunto": "procedencia", "resumenes": resumen, "detalle": filas}
    ruta = DIR_RESULTADOS / f"procedencia_{(args.modelo or config.llm_modelo).replace('/', '_')}.json"
    ruta.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDetalle guardado en {ruta}")


if __name__ == "__main__":
    main()
