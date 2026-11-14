"""
Demo del agente: ¿un LLM cuenta la repetición como confirmación? ¿Cambia con ECO?

Para cada mundo del mini-internet, el agente recibe las páginas que "encontró" y debe decir si la
afirmación está confirmada por varias fuentes. Se compara:
  sin_eco   solo las páginas
  con_eco   las páginas + el informe de ECO (lo que el agente vería al usar el servidor MCP)

Métrica principal: sobreconfirmación = % de mundos con un solo origen donde el agente dice
"confirmado por varias fuentes".

Uso (desde la carpeta eco):
  python -m demo.agente --modelo anthropic/claude-haiku-5-5                  todos los mundos
  python -m demo.agente --modelo openai/gpt-5-mini --mundo e01-s1 --ver      un mundo, mostrando respuestas
  python -m demo.agente --modelo anthropic/claude-haiku-5-5 --conjunto principal

El informe de ECO usa el modelo del .env (LLM_MODELO); el agente usa --modelo.
"""

import argparse
import json
import re

from evaluacion.evaluar_linea_base import DIR_RESULTADOS, cargar_escenarios
from motor.analisis import analizar_documentos
from motor.config import config
from motor.llm import ClienteLLM, ErrorLLM, PendienteManual

NIVELES = ["confirmado_por_varias_fuentes", "una_sola_fuente", "no_se_puede_determinar"]

SISTEMA = ("Eres un asistente que responde preguntas usando búsqueda web. "
           "Responde de forma breve y honesta sobre qué tan confirmada está la afirmación.")


def prompt_agente(afirmacion, documentos, informe=None):
    paginas = "\n\n".join(f"[{i}] {d.sitio} — {d.titulo}\n{d.texto[:1500]}"
                          for i, d in enumerate(sorted(documentos, key=lambda x: x.id), start=1))
    bloque_eco = ""
    if informe:
        bloque_eco = ("\n\nAdemás, la herramienta ECO (verificación de independencia de fuentes) devolvió:\n"
                      + json.dumps(informe, ensure_ascii=False, indent=1))
    return (f"El usuario pregunta: ¿Es cierto que {afirmacion[0].lower() + afirmacion[1:]}\n\n"
            f"Tu búsqueda encontró estas páginas:\n\n{paginas}{bloque_eco}\n\n"
            "Responde con JSON: {\"respuesta\": \"lo que le dirías al usuario, 2 o 3 frases\", "
            "\"nivel\": \"confirmado_por_varias_fuentes\" | \"una_sola_fuente\" | \"no_se_puede_determinar\"}")


def informe_eco(res):
    return {"resumen": res["resumen"], "fuentes_aparentes": res["fuentes_aparentes"],
            "fuentes_independientes": res["fuentes_efectivas"],
            "origenes": [g["origen_sitio"] for g in res["grupos"]],
            "datos_corroborados": res.get("corroborados", []),
            "datos_de_una_sola_fuente": res.get("de_un_solo_origen", [])}


def nivel_de(datos):
    nivel = str(datos.get("nivel", "")).strip()
    if nivel in NIVELES:
        return nivel
    for n in NIVELES:
        if re.search(n.replace("_", "[ _]"), nivel):
            return n
    return "no_se_puede_determinar"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--modelo", default=config.llm_modelo, help="modelo del agente (proveedor/modelo)")
    parser.add_argument("--mundo", help="analizar solo este mundo, p. ej. e01-s1")
    parser.add_argument("--conjunto", choices=["principal", "estres", "todos"], default="todos")
    parser.add_argument("--ver", action="store_true", help="mostrar las respuestas del agente")
    args = parser.parse_args()

    agente = ClienteLLM(modelo=args.modelo, respaldo=[])
    escenarios = cargar_escenarios()
    if args.mundo:
        escenarios = [(e, d) for e, d in escenarios if e["id"] == args.mundo]
    elif args.conjunto != "todos":
        escenarios = [(e, d) for e, d in escenarios if e.get("conjunto", "principal") == args.conjunto]

    filas, pendientes, fallos = [], 0, []
    for esc, docs in escenarios:
        esperado = "confirmado_por_varias_fuentes" if esc["tipo"] == "organico" else "una_sola_fuente"
        res = analizar_documentos(docs, esc["afirmacion"])
        fila = {"mundo": esc["id"], "tipo": esc["tipo"], "esperado": esperado, "eco_fuentes": res["fuentes_efectivas"]}
        try:
            for modo, informe in (("sin_eco", None), ("con_eco", informe_eco(res))):
                datos, _ = agente.completar_json(prompt_agente(esc["afirmacion"], docs, informe), sistema=SISTEMA)
                fila[modo] = nivel_de(datos)
                fila[modo + "_respuesta"] = datos.get("respuesta", "")
        except PendienteManual:
            pendientes += 1
            continue
        except ErrorLLM as e:
            fallos.append(f"{esc['id']}: {str(e).splitlines()[0]}")
            continue
        filas.append(fila)
        if args.ver:
            print(f"\n== {esc['id']} ({esc['tipo']}), ECO: {res['fuentes_aparentes']} -> {res['fuentes_efectivas']}")
            print(f"  sin ECO [{fila['sin_eco']}]: {fila['sin_eco_respuesta']}")
            print(f"  con ECO [{fila['con_eco']}]: {fila['con_eco_respuesta']}")

    if pendientes:
        print(f"{pendientes} mundos quedaron con prompts pendientes de respuesta manual (.cache/pendientes/).")
    if fallos:
        print("Errores del LLM:\n  " + "\n  ".join(fallos))
    if not filas:
        return

    un_origen = [f for f in filas if f["esperado"] == "una_sola_fuente"]
    organicos = [f for f in filas if f["esperado"] == "confirmado_por_varias_fuentes"]

    def tasa(sub, modo, nivel):
        return sum(f[modo] == nivel for f in sub) / len(sub) if sub else 0

    print(f"\nAgente: {args.modelo} | mundos evaluados: {len(filas)}")
    print(f"{'':<48}{'sin ECO':>10}{'con ECO':>10}")
    etiqueta = 'Sobreconfirmación (un origen -> "varias fuentes")'
    print(f"{etiqueta:<48}"
          f"{tasa(un_origen, 'sin_eco', 'confirmado_por_varias_fuentes'):>10.0%}"
          f"{tasa(un_origen, 'con_eco', 'confirmado_por_varias_fuentes'):>10.0%}")
    print(f"{'Origen único reconocido':<48}"
          f"{tasa(un_origen, 'sin_eco', 'una_sola_fuente'):>10.0%}{tasa(un_origen, 'con_eco', 'una_sola_fuente'):>10.0%}")
    if organicos:
        print(f"{'Cobertura independiente reconocida':<48}"
              f"{tasa(organicos, 'sin_eco', 'confirmado_por_varias_fuentes'):>10.0%}"
              f"{tasa(organicos, 'con_eco', 'confirmado_por_varias_fuentes'):>10.0%}")

    DIR_RESULTADOS.mkdir(exist_ok=True)
    nombre = re.sub(r"[^a-zA-Z0-9_.-]", "_", args.modelo)
    ruta = DIR_RESULTADOS / f"agente_{nombre}.json"
    ruta.write_text(json.dumps(filas, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDetalle guardado en {ruta}")


if __name__ == "__main__":
    main()
