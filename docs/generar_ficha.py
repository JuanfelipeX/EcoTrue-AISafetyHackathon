"""
Genera la ficha técnica (PDF, máximo 2 páginas) a partir de los resultados de la evaluación.

Uso (desde la carpeta eco):
  python -m docs.generar_ficha                                     Sonnet vía Claude Code (desarrollo + prueba)
  python -m docs.generar_ficha --modelo claudecode/haiku
  python -m docs.generar_ficha --equipo "Nombre del equipo" --integrantes "Ana, Luis, Sadid" --repo "https://…"

Antes hay que correr: python -m evaluacion.evaluar --modelo <modelo> [--conjunto prueba]
y python -m demo.agente --modelo <agente> para el párrafo del agente.
Salida: docs/ficha_tecnica_ECO.pdf
"""

import argparse
import json
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

RAIZ = Path(__file__).resolve().parent.parent
RESULTADOS = RAIZ / "evaluacion" / "resultados"

TINTA = colors.HexColor("#1F1F1F")
GRAFITO = colors.HexColor("#3A3A3A")
ACENTO = colors.HexColor("#B4532A")
SUAVE = colors.HexColor("#F4ECE6")
LINEA = colors.HexColor("#D8CFC8")
GRIS = colors.HexColor("#6B6560")

TIPOS = [("organico", "Orgánico (4–5 fuentes reales)"), ("literal", "Copias literales"),
         ("parafrasis", "Paráfrasis sin datos nuevos"), ("comunicado", "Comunicado replicado"),
         ("fabricado_literal", "Estrés: copia + datos inventados"),
         ("fabricado_parafrasis", "Estrés: paráfrasis + datos inventados")]
PRINCIPAL = [t for t, _ in TIPOS[:4]]
ESTRES = [t for t, _ in TIPOS[4:]]


def registrar_fuentes():
    """Usa DejaVu o Arial si existen (para tildes); si no, Helvetica."""
    candidatos = [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
        ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
        ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ]
    for normal, negrita in candidatos:
        if Path(normal).exists() and Path(negrita).exists():
            pdfmetrics.registerFont(TTFont("F", normal))
            pdfmetrics.registerFont(TTFont("FB", negrita))
            pdfmetrics.registerFontFamily("F", normal="F", bold="FB", italic="F", boldItalic="FB")
            return "F", "FB"
    return "Helvetica", "Helvetica-Bold"


def pct(x):
    return "—" if x is None else f"{x * 100:.0f} %"


def limpio(modelo):
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", modelo)


def cargar(nombre):
    ruta = RESULTADOS / nombre
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None


def global_de(resumenes, metodo, tipos):
    if not resumenes:
        return None
    sub = [resumenes[metodo][t] for t in tipos if t in resumenes.get(metodo, {})]
    n = sum(x["n"] for x in sub)
    return (sum(x["exactitud"] * x["n"] for x in sub) / n) if n else None


def exactitud(resumenes, metodo, tipo):
    if not resumenes or tipo not in resumenes.get(metodo, {}):
        return None
    return resumenes[metodo][tipo]["exactitud"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--modelo", default="claudecode/sonnet", help="modelo extractor principal de la ficha")
    parser.add_argument("--agente", default="claudecode/haiku", help="modelo usado en demo.agente")
    parser.add_argument("--equipo", default="Equipo ECO")
    parser.add_argument("--integrantes", default="")
    parser.add_argument("--repo", default="")
    args = parser.parse_args()

    nombre = limpio(args.modelo)
    dev = cargar(f"comparacion_{nombre}.json")
    prueba = cargar(f"comparacion_{nombre}__prueba.json")
    if not dev:
        raise SystemExit(f"Falta comparacion_{nombre}.json. Corra: python -m evaluacion.evaluar --modelo {args.modelo}")
    agente = cargar(f"agente_{limpio(args.agente)}.json")
    rd, rp = dev["resumenes"], (prueba or {}).get("resumenes")

    N, B = registrar_fuentes()
    titulo = ParagraphStyle("t", fontName=B, fontSize=15, leading=18, textColor=TINTA)
    sub = ParagraphStyle("s", fontName=N, fontSize=8.5, leading=11, textColor=GRIS, spaceAfter=4)
    h = ParagraphStyle("h", fontName=B, fontSize=10, leading=12, textColor=ACENTO, spaceBefore=6, spaceAfter=2)
    p = ParagraphStyle("p", fontName=N, fontSize=8.3, leading=10.6, textColor=GRAFITO, spaceAfter=2)
    celda = ParagraphStyle("c", fontName=N, fontSize=7.7, leading=9.4, textColor=GRAFITO)
    celdab = ParagraphStyle("cb", parent=celda, fontName=B, textColor=TINTA)
    cab = ParagraphStyle("ch", parent=celda, fontName=B, textColor=colors.white)

    def tabla(filas, anchos, negrita_ultimas=0):
        datos = [[Paragraph(c, cab) for c in filas[0]]]
        for i, f in enumerate(filas[1:], start=1):
            estilo = celdab if i > len(filas) - 1 - negrita_ultimas else celda
            datos.append([Paragraph(c, celdab if j == 0 else estilo) for j, c in enumerate(f)])
        t = Table(datos, colWidths=anchos)
        st = [("BACKGROUND", (0, 0), (-1, 0), GRAFITO), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
              ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINEA), ("TOPPADDING", (0, 0), (-1, -1), 2.2),
              ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2), ("LEFTPADDING", (0, 0), (-1, -1), 4)]
        st += [("BACKGROUND", (0, i), (-1, i), SUAVE) for i in range(2, len(datos), 2)]
        t.setStyle(TableStyle(st))
        return t

    filas = [["Tipo de mundo", "n des. / prueba", "Línea base (des.)", "ECO híbrido (des.)",
              "Línea base (prueba)", "ECO híbrido (prueba)"]]
    for t, etiqueta in TIPOS:
        if t not in rd["linea_base"]:
            continue
        n_p = rp["linea_base"][t]["n"] if rp and t in rp["linea_base"] else 0
        filas.append([etiqueta, f"{rd['linea_base'][t]['n']} / {n_p}",
                      pct(exactitud(rd, "linea_base", t)), pct(exactitud(rd, "hibrido", t)),
                      pct(exactitud(rp, "linea_base", t)), pct(exactitud(rp, "hibrido", t))])
    for etiqueta, tipos in (("Global principal", PRINCIPAL), ("Global estrés", ESTRES)):
        filas.append([etiqueta, "", pct(global_de(rd, "linea_base", tipos)), pct(global_de(rd, "hibrido", tipos)),
                      pct(global_de(rp, "linea_base", tipos)), pct(global_de(rp, "hibrido", tipos))])

    otros = []
    for ruta in sorted(RESULTADOS.glob("comparacion_*.json")):
        d = json.loads(ruta.read_text(encoding="utf-8"))
        if d.get("modelo", "").startswith("manual/"):
            continue
        conj = "prueba" if ruta.stem.endswith("__prueba") else "desarrollo"
        otros.append(f"{d['modelo']} ({conj}) {pct(global_de(d['resumenes'], 'hibrido', PRINCIPAL))}")
    historial = []
    for v in ("v1", "v2"):
        d = cargar(f"historial/comparacion_{nombre}__{v}.json")
        if d:
            historial.append(f"{v} {pct(global_de(d['resumenes'], 'hibrido', PRINCIPAL))}")
    historial.append(f"v3 {pct(global_de(rd, 'hibrido', PRINCIPAL))}")

    s = []
    s.append(Paragraph("ECO — ¿Cuántas fuentes hay de verdad detrás de una afirmación?", titulo))
    linea_equipo = f"{args.equipo}" + (f" · {args.integrantes}" if args.integrantes else "")
    s.append(Paragraph(f"Ficha técnica · Frente 4: Defensa epistémica · {linea_equipo}"
                       + (f" · Repositorio: {args.repo}" if args.repo else ""), sub))

    s.append(Paragraph("1. Amenaza", h))
    s.append(Paragraph(
        "La IA abarata clonar una afirmación en decenas de sitios y parafrasearla para que no parezca copia. "
        "Las personas y los agentes con búsqueda web toman la repetición como corroboración: cinco páginas "
        "parecidas se leen como cinco fuentes, y el agente transmite esa falsa confirmación. Vector concreto: "
        "<b>lavado de fuentes</b>, un solo origen que aparenta muchas fuentes independientes.", p))

    s.append(Paragraph("2. Defensa", h))
    s.append(Paragraph(
        "<b>(a) Hechos atómicos:</b> una llamada a un LLM por conjunto de páginas lista los datos verificables, "
        "marca en qué páginas aparece cada uno (las paráfrasis cuentan como un solo hecho) y separa las frases "
        "<i>sobre la noticia</i> (quién la informó, que es tendencia) de los datos <i>sobre el suceso</i>. "
        "<b>(b) Regla de independencia</b> (sin LLM, auditable): en orden cronológico, una página es fuente "
        "independiente solo si aporta al menos un dato no publicado antes. <b>(c) Guardia híbrida:</b> texto casi "
        "idéntico a una página anterior (TF-IDF de caracteres, coseno ≥ 0,6) cuenta como copia aunque agregue datos. "
        "<b>(d) Salida:</b> fuentes aparentes frente a independientes, origen, árbol de copias y datos corroborados "
        "frente a datos de una sola fuente. Se entrega como <b>extensión de Chrome</b> (personas), <b>servidor MCP</b> "
        "(agentes), <b>panel web</b> y <b>API</b>, con cliente LLM agnóstico (OpenAI, Anthropic, OpenRouter, Ollama "
        "local, Claude Code) y respuestas en caché para auditoría y uso sin conexión.", p))

    s.append(Paragraph("3. Cómo se evaluó", h))
    s.append(Paragraph(
        "Mini-internet sintético con respuesta conocida: <b>desarrollo</b>, 36 mundos de 6 eventos (203 páginas), usado "
        "para diseñar y ajustar ECO; <b>prueba retenida</b>, 18 mundos de 3 eventos nuevos (101 páginas) escritos después "
        "del último ajuste y evaluados una sola vez. Tipos: cobertura orgánica, copias literales, paráfrasis, comunicado "
        "replicado y dos ataques (copias que inventan testimonios y cifras). Métrica: exactitud del conteo de fuentes "
        "independientes y fusión falsa de medios independientes. Línea base: similitud de texto + enlaces. "
        f"Extractor principal: <b>{args.modelo}</b>, llamado por la CLI de Claude Code sin herramientas y desde una carpeta "
        "vacía (no ve el corpus ni las respuestas).", p))

    s.append(Paragraph("4. Resultados", h))
    s.append(tabla(filas, [5.0 * cm, 2.1 * cm, 2.4 * cm, 2.6 * cm, 2.6 * cm, 2.8 * cm], negrita_ultimas=2))
    s.append(Spacer(1, 3))
    s.append(Paragraph(
        "<b>Hallazgo:</b> la similitud de texto no detecta paráfrasis, y ningún umbral acierta a la vez orgánico y "
        "paráfrasis (umbral 0,5: 17 % y 67 %; 0,6: 100 % y 33 %). ECO por hechos sí, sin fusionar medios independientes "
        f"(fusión falsa {pct(rd['hibrido']['organico']['fusion_falsa'])}). <b>Global principal por modelo:</b> "
        + "; ".join(otros) + ". Un modelo local de 7B queda por debajo de la línea base: la calidad del extractor manda.", p))
    s.append(Paragraph(
        "<b>Honestidad metodológica:</b> el prompt se ajustó dos veces mirando errores del conjunto de desarrollo "
        f"(global principal: {', '.join(historial)}): v2 separa las frases de atribución; v3 incluye comentarios sobre la "
        "difusión y pide no partir un dato en sub-detalles. Por eso el 100 % de desarrollo está sobreajustado y la cifra "
        "a reportar es la del conjunto de prueba retenido. Con n = 3 por tipo, cada mundo pesa 33 puntos.", p))
    if agente:
        un = [f for f in agente if f["esperado"] == "una_sola_fuente"]
        org_f = [f for f in agente if f["esperado"] != "una_sola_fuente"]

        def tasa(sub_, modo, nivel):
            return sum(f[modo] == nivel for f in sub_) / max(len(sub_), 1)
        s.append(Paragraph(
            f"<b>Agente ({args.agente}):</b> en {len(un)} mundos con un solo origen, dijo «confirmado por varias fuentes» "
            f"en el {pct(tasa(un, 'sin_eco', 'confirmado_por_varias_fuentes'))} sin ECO y en el "
            f"{pct(tasa(un, 'con_eco', 'confirmado_por_varias_fuentes'))} con el informe de ECO; reconoció el origen único "
            f"en {pct(tasa(un, 'sin_eco', 'una_sola_fuente'))} → {pct(tasa(un, 'con_eco', 'una_sola_fuente'))}. En "
            f"{len(org_f)} mundos orgánicos reconoció cobertura independiente en "
            f"{pct(tasa(org_f, 'sin_eco', 'confirmado_por_varias_fuentes'))} → "
            f"{pct(tasa(org_f, 'con_eco', 'confirmado_por_varias_fuentes'))}.", p))

    s.append(Paragraph("5. Límites", h))
    s.append(Paragraph(
        "<b>Ataque abierto:</b> copias reescritas que además inventan detalles distintos en cada página se cuentan como "
        "fuentes independientes (0 %). La guardia híbrida solo detiene la versión barata (copiar y añadir). "
        "<b>Independencia no es verdad:</b> varias fuentes independientes pueden equivocarse. <b>Datos sintéticos:</b> "
        "eventos y paráfrasis escritos a mano, muestras pequeñas; no se probó en la web real y la extensión solo encuentra "
        "páginas relacionadas dentro del mini-internet (el MCP y el panel aceptan URLs arbitrarias). <b>Dependencia del "
        "extractor:</b> con un modelo pequeño los errores de alineación cambian el conteo.", p))

    s.append(Paragraph("6. Riesgo de doble uso", h))
    s.append(Paragraph(
        "Un atacante podría usar ECO como oráculo para ajustar sus copias hasta que pasen como independientes. "
        "Mitigaciones: no publicar umbrales de producción, limitar consultas masivas y combinar con señales que el "
        "atacante no controla (firmas de procedencia como C2PA, historial del dominio, patrones temporales). "
        "El corpus es ficticio, está marcado como sintético y no contiene personas ni medios reales. "
        "No se analizaron sistemas de terceros.", p))

    s.append(Paragraph("7. Reproducibilidad y créditos", h))
    s.append(Paragraph(
        "<font face='Courier'>python -m pruebas.prueba_humo; python -m evaluacion.evaluar --modelo "
        f"{args.modelo} [--conjunto prueba]; python -m demo.agente --modelo {args.agente}</font>. Resultados, historial y "
        "respuestas del LLM en el repositorio. Código escrito con asistencia de Claude (Anthropic): se declara como "
        "material generado con IA. Bibliotecas: scikit-learn, FastAPI, SDK de MCP, BeautifulSoup, SDK de OpenAI y "
        "Anthropic, ReportLab.", p))

    salida = RAIZ / "docs" / "ficha_tecnica_ECO.pdf"
    doc = SimpleDocTemplate(str(salida), pagesize=letter, leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                            topMargin=1.2 * cm, bottomMargin=1.1 * cm, title="ECO — Ficha técnica")
    doc.build(s)
    try:
        from pypdf import PdfReader
        paginas = len(PdfReader(str(salida)).pages)
        print(f"Ficha generada: {salida} ({paginas} página{'s' if paginas != 1 else ''})")
        if paginas > 2:
            print("ATENCIÓN: supera el máximo de 2 páginas. Recorte texto antes de enviar.")
    except ImportError:
        print(f"Ficha generada: {salida}")


if __name__ == "__main__":
    main()
