"""
Ficha técnica con la plantilla oficial de DefAcc 2026 (máx. 2 páginas), en español e inglés.

Uso (desde la carpeta eco):
  python -m docs.generar_ficha_plantilla --contacto correo@ejemplo.com
Salida: docs/ficha_DefAcc_ECO_ES.pdf y docs/ficha_DefAcc_ECO_EN.pdf
"""

import argparse
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from docs.arquitectura import diagrama

RAIZ = Path(__file__).resolve().parent
FUENTES = Path("C:/Windows/Fonts")
TINTA = colors.HexColor("#1F1F1F")
GRIS = colors.HexColor("#6B6B6B")
BORDE = colors.HexColor("#E3E3D8")
CABEZA = colors.HexColor("#F3F3F1")
BARRA = colors.HexColor("#D9D9D2")

REPO = "https://github.com/SadidRomero77/eco"
WEB = "https://eco.kibosecondbrain.com"

T = {
    "es": {
        "archivo": "ficha_DefAcc_ECO_ES.pdf",
        "pie": "Ficha técnica DefAcc 2026 · ECO", "pagina": "Página {} de 2",
        "cabecera": "Hackathon DefAcc 2026 · Ficha técnica",
        "titulo": "ECO",
        "linea": "Mide cuántas fuentes independientes hay detrás de una noticia, una foto o una nota de voz, antes de que la compartas.",
        "equipo": "<b>Equipo:</b> Sadid Romero, Juan Felipe Jimenez, Ana Maria Vargas · ECO TRACE Team",
        "track": "<b>Track:</b> 4. Defensa epistémica",
        "enlaces": ["Repositorio", "Demo", "Contacto"],
        "demo": f"En vivo: {WEB}<br/>MCP: {WEB}/mcp",
        "resumen_t": "Resumen",
        "resumen": "Con IA es casi gratis clonar una noticia en decenas de sitios, falsear la fecha de una foto o clonar una voz, "
                   "y personas y agentes de IA cuentan esa repetición como confirmación. Construimos ECO: una web, una extensión "
                   "y un servidor MCP que miden cuántas fuentes independientes respaldan una afirmación, verifican firmas C2PA y "
                   "detectan voces sintéticas. En mundos de prueba nunca vistos contó bien las fuentes el <b>92 %</b> de las veces "
                   "(comparar textos: 83 %).",
        "s1_t": "1. La amenaza",
        "s1": "<b>Lavado de fuentes:</b> una afirmación se copia y se parafrasea con IA en muchos sitios, se ilustra con una "
              "foto ajena o de fecha falsa, o llega como audio de WhatsApp con voz clonada. Un buscador muestra ocho páginas y "
              "parecen ocho fuentes; un agente de IA con búsqueda web responde «varias fuentes lo confirman». Perjudica a quien "
              "recibe y reenvía rumores, sobre todo en América Latina, donde circulan por WhatsApp, que borra los metadatos. Los "
              "verificadores no escalan y los detectores de voz de laboratorio fallan con audio comprimido.",
        "s2_t": "2. Lo que construimos",
        "s2": "ECO no dice qué es verdad: mide cuánta evidencia independiente hay y de dónde viene. Un modelo (Claude en Amazon "
              "Bedrock) extrae los datos verificables de cada página; luego una <b>regla auditable, sin LLM</b>, recorre las páginas "
              "en orden cronológico y solo cuenta como fuente a la que aporta al menos un dato que nadie había publicado. Dos "
              "refuerzos: las <b>firmas C2PA</b> y una huella visual de cada foto delatan copias que reutilizan una imagen ajena o "
              "fingen una fecha anterior, y un <b>detector AASIST-L</b> que reentrenamos con compresión tipo WhatsApp estima si una voz "
              "es sintética. Se usa en la web (español e inglés), en una extensión de Chrome o desde cualquier agente vía MCP. "
              "Entra un tema, una URL, una nota de voz o una captura; sale una conclusión en una frase, el árbol de origen y la "
              "fuente recomendada para leer primero.",
        "fig": "<b>Figura 1.</b> Arquitectura de ECO. Cuatro tipos de entrada pasan por una ingesta segura y un motor de cinco "
               "pasos; el resultado llega a la web, la extensión, el servidor MCP y un informe para compartir. Corre en AWS detrás "
               "de Cloudflare.",
        "s3_t": "3. Cómo lo evaluamos",
        "s3": "Creamos «mundos» sintéticos (medios, personas y lugares ficticios), cada uno con su respuesta correcta guardada "
              "aparte: 36 para ajustar, 18 de eventos nuevos como examen final evaluado una sola vez, y 12 con fotos firmadas. "
              "Comparamos con la línea base de agrupar páginas por similitud de texto. La métrica es el <b>conteo exacto de fuentes "
              "independientes</b>, porque es justo lo que el lavado de fuentes falsea. La voz se midió con In-the-Wild: 1 200 "
              "audios de 17 personas no vistas, limpios y comprimidos.",
        "s4_t": "4. Resultados",
        "tabla": [["Métrica", "Línea base", "ECO", "Diferencia"],
                  ["Conteo exacto de fuentes (examen final)", "83 %", "92 %", "+9 pts"],
                  ["Paráfrasis reconocidas como copia", "33 %", "67 %", "+33 pts"],
                  ["Agente dice «confirmado» con un solo origen ↓", "51 %", "22 %", "−29 pts"],
                  ["Copias reescritas que reutilizan la foto firmada", "0 %", "100 %", "+100 pts"],
                  ["Error del detector de voz, nota tipo WhatsApp ↓", "49,7 %", "28,7 %", "−21 pts"]],
        "tabla_pie": "<b>Tabla 1.</b> Examen final: 12 mundos principales, 3 por tipo. Agente: Claude Haiku en 54 mundos, sin y con "
                     "el informe de ECO. Fotos: 12 mundos con firma C2PA, línea base solo texto. Voz: tasa de error igual (EER) con "
                     "compresión Opus de 16 kbps; línea base, AASIST-L tal como se publica. ↓ = menos es mejor.",
        "s4": "<b>Hallazgo:</b> medir independencia de datos, y no parecido de texto, desactiva las paráfrasis sin fusionar medios "
              "independientes. <b>Dónde falla:</b> si cada copia reescribe e inventa detalles distintos sin reutilizar la foto, ECO "
              "también la cuenta como fuente. No reportamos el 100 % de los mundos de práctica: estaba sobreajustado.",
        "s5_t": "5. Límites y riesgo de doble uso",
        "s5": "Independiente no significa verdadero. C2PA prueba quién firmó, no qué es cierto; casi nada viene firmado y usamos "
              "una autoridad de prueba. Una agencia publicada después de una copia puede verse como repetición. La voz solo se "
              "midió en inglés y falla 29 de cada 100 veces; los filtros forenses de imagen no están evaluados. <b>Doble uso:</b> "
              "alguien podría pulir copias hasta que pasen; lo mitigamos con límites por IP y tope diario, sin publicar umbrales, "
              "y presentamos cada veredicto como alerta, nunca como acusación.",
        "ref_t": "Referencias",
    },
    "en": {
        "archivo": "ficha_DefAcc_ECO_EN.pdf",
        "pie": "DefAcc 2026 technical sheet · ECO", "pagina": "Page {} of 2",
        "cabecera": "DefAcc Hackathon 2026 · Technical sheet",
        "titulo": "ECO",
        "linea": "Measures how many independent sources stand behind a news story, a photo or a voice note, before you share it.",
        "equipo": "<b>Team:</b> Sadid Romero, Juan Felipe Jimenez, Ana Maria Vargas · ECO TRACE Team",
        "track": "<b>Track:</b> 4. Epistemic defense",
        "enlaces": ["Repository", "Demo", "Contact"],
        "demo": f"Live: {WEB}<br/>MCP: {WEB}/mcp",
        "resumen_t": "Summary",
        "resumen": "AI makes it almost free to clone a story across dozens of sites, fake a photo's date or clone a voice, and "
                   "both people and AI agents count that repetition as confirmation. We built ECO: a web app, a browser extension "
                   "and an MCP server that measure how many independent sources back a claim, verify C2PA signatures and detect "
                   "synthetic voices. On unseen test worlds it counted sources correctly <b>92 %</b> of the time (text similarity: "
                   "83 %).",
        "s1_t": "1. The threat",
        "s1": "<b>Source laundering:</b> one claim is copied and AI-paraphrased across many sites, illustrated with someone else's "
              "photo or a false date, or arrives as a WhatsApp voice note with a cloned voice. A search engine shows eight pages "
              "and they look like eight sources; a web-searching AI agent answers \"several sources confirm it\". It harms whoever "
              "receives and forwards rumors, especially in Latin America, where they spread on WhatsApp, which strips metadata. "
              "Human fact-checkers do not scale, and lab-trained voice detectors fail on compressed audio.",
        "s2_t": "2. What we built",
        "s2": "ECO does not say what is true: it measures how much independent evidence exists and where it comes from. A model "
              "(Claude on Amazon Bedrock) extracts the checkable facts on each page; then an <b>auditable, LLM-free rule</b> walks "
              "the pages in chronological order and counts a page as a source only if it adds at least one fact nobody had "
              "published before. Two reinforcements: <b>C2PA signatures</b> and a perceptual hash of each photo expose copies that "
              "reuse another outlet's image or fake an earlier date, and an <b>AASIST-L detector</b> we retrained with WhatsApp-like "
              "compression estimates whether a voice is synthetic. It runs on the web (Spanish and English), as a Chrome "
              "extension, or from any agent via MCP. Input: a topic, URL, voice note or screenshot. Output: a one-sentence "
              "verdict, the origin tree and the recommended source to read first.",
        "fig": "<b>Figure 1.</b> ECO architecture. Four input types go through safe ingestion and a five-step engine; results reach "
               "the web app, the extension, the MCP server and a shareable report. Runs on AWS behind Cloudflare.",
        "s3_t": "3. How we evaluated it",
        "s3": "We built synthetic \"worlds\" (fictitious outlets, people and places), each with its ground truth stored apart: 36 "
              "for tuning, 18 from new events as a final exam evaluated once, and 12 with signed photos. The baseline groups pages "
              "by text similarity. The metric is the <b>exact count of independent sources</b>, because that is precisely what "
              "source laundering fakes. Voice was measured on In-the-Wild: 1,200 clips from 17 unseen speakers, clean and "
              "compressed.",
        "s4_t": "4. Results",
        "tabla": [["Metric", "Baseline", "ECO", "Difference"],
                  ["Exact source count (final exam)", "83 %", "92 %", "+9 pts"],
                  ["Paraphrases recognized as copies", "33 %", "67 %", "+33 pts"],
                  ["Agent says \"confirmed\" with a single origin ↓", "51 %", "22 %", "−29 pts"],
                  ["Rewritten copies reusing the signed photo", "0 %", "100 %", "+100 pts"],
                  ["Voice detector error, WhatsApp-like note ↓", "49.7 %", "28.7 %", "−21 pts"]],
        "tabla_pie": "<b>Table 1.</b> Final exam: 12 main worlds, 3 per type. Agent: Claude Haiku on 54 worlds, without and with "
                     "ECO's report. Photos: 12 C2PA-signed worlds, baseline is text only. Voice: equal error rate (EER) under 16 "
                     "kbps Opus compression; baseline is AASIST-L as published. ↓ = lower is better.",
        "s4": "<b>Key finding:</b> measuring independence of facts, not textual similarity, defeats paraphrasing without merging "
              "independent outlets. <b>Where it fails:</b> if each copy rewrites and invents different details without reusing the "
              "photo, ECO also counts it as a source. We do not report the 100 % on tuning worlds: it was overfit.",
        "s5_t": "5. Limits and dual-use risk",
        "s5": "Independent does not mean true. C2PA proves who signed, not what is true; almost nothing is signed and we use a "
              "demo certificate authority. A wire agency published after a copy can look like a repetition. Voice was only "
              "measured in English and errs 29 times in 100; image forensics are unevaluated. <b>Dual use:</b> someone could polish "
              "copies until they pass; we mitigate with per-IP limits and a daily cap, unpublished thresholds, and we frame every "
              "verdict as an alert, never an accusation.",
        "ref_t": "References",
    },
}

REFERENCIAS = [
    "C2PA (2024). <i>C2PA Technical Specification 2.1</i>. Coalition for Content Provenance and Authenticity, c2pa.org.",
    "Jung, J. et al. (2022). AASIST: Audio anti-spoofing using integrated spectro-temporal graph attention networks. <i>ICASSP</i>.",
    "Müller, N. et al. (2022). Does audio deepfake detection generalize? (In-the-Wild dataset). <i>Interspeech</i>.",
    "Krawetz, N. (2007). A picture's worth: digital image analysis and forensics. <i>Black Hat</i>.",
]


def palabras(html):
    return len(re.sub(r"<[^>]+>", " ", html).split())


def registrar():
    for nombre, archivo in (("Serif", "georgia.ttf"), ("SerifI", "georgiai.ttf"), ("Sans", "segoeui.ttf"),
                            ("SansB", "segoeuib.ttf"), ("SansI", "segoeuii.ttf"), ("SansBI", "segoeuiz.ttf")):
        pdfmetrics.registerFont(TTFont(nombre, str(FUENTES / archivo)))
    pdfmetrics.registerFontFamily("Sans", normal="Sans", bold="SansB", italic="SansI", boldItalic="SansBI")


def construir(idioma, contacto):
    t = T[idioma]
    salida = RAIZ / t["archivo"]
    doc = SimpleDocTemplate(str(salida), pagesize=letter, leftMargin=2.1 * cm, rightMargin=2.1 * cm,
                            topMargin=1.7 * cm, bottomMargin=1.6 * cm, title=f"ECO · {t['cabecera']}",
                            author="ECO TRACE Team")
    ancho = doc.width
    cab = ParagraphStyle("cab", fontName="SansI", fontSize=10, leading=13, textColor=TINTA)
    tit = ParagraphStyle("tit", fontName="Serif", fontSize=26, leading=30, textColor=TINTA, spaceBefore=2, spaceAfter=3)
    lin = ParagraphStyle("lin", fontName="SansI", fontSize=10.5, leading=14, textColor=TINTA, spaceAfter=5)
    p = ParagraphStyle("p", fontName="Sans", fontSize=10, leading=13.6, textColor=TINTA, spaceAfter=3)
    h = ParagraphStyle("h", fontName="Serif", fontSize=15, leading=18, textColor=TINTA, spaceBefore=8, spaceAfter=4)
    pie = ParagraphStyle("pie", fontName="Sans", fontSize=8.8, leading=11.6, textColor=TINTA, spaceBefore=3, spaceAfter=3)
    celda = ParagraphStyle("c", fontName="Sans", fontSize=9, leading=11.4, textColor=TINTA)
    celda_c = ParagraphStyle("cc", parent=celda, textColor=GRIS)
    ref = ParagraphStyle("r", fontName="Sans", fontSize=8.2, leading=10.4, textColor=GRIS, leftIndent=8, firstLineIndent=-8)

    def tabla(filas, anchos, cabeza=celda_c, num=False):
        datos = [[Paragraph(c, cabeza) for c in filas[0]]] + [[Paragraph(c, celda) for c in f] for f in filas[1:]]
        tb = Table(datos, colWidths=anchos)
        estilo = [("GRID", (0, 0), (-1, -1), 0.6, BORDE), ("BACKGROUND", (0, 0), (-1, 0), CABEZA),
                  ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                  ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5), ("LEFTPADDING", (0, 0), (-1, -1), 6)]
        tb.setStyle(TableStyle(estilo))
        return tb

    def destacado(html):
        tb = Table([[Paragraph(html, p)]], colWidths=[ancho])
        tb.setStyle(TableStyle([("LINEBEFORE", (0, 0), (0, 0), 3, BARRA), ("LEFTPADDING", (0, 0), (-1, -1), 12),
                                ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
        return tb

    s = [Paragraph(t["cabecera"], cab), Paragraph(t["titulo"], tit), Paragraph(t["linea"], lin),
         Paragraph(t["equipo"], p), Paragraph(t["track"], p), Spacer(1, 4),
         tabla([t["enlaces"], [REPO, t["demo"], contacto or "—"]], [ancho * 0.36, ancho * 0.38, ancho * 0.26]),
         Paragraph(t["resumen_t"], h), destacado(t["resumen"]),
         Paragraph(t["s1_t"], h), Paragraph(t["s1"], p),
         Paragraph(t["s2_t"], h), Paragraph(t["s2"], p),
         KeepTogether([Spacer(1, 3), diagrama(ancho, "Sans", "SansB", idioma), Paragraph(t["fig"], pie)]),
         Paragraph(t["s3_t"], h), Paragraph(t["s3"], p),
         Paragraph(t["s4_t"], h),
         tabla(t["tabla"], [ancho * 0.52, ancho * 0.16, ancho * 0.16, ancho * 0.16]),
         Paragraph(t["tabla_pie"], pie), Paragraph(t["s4"], p),
         Paragraph(t["s5_t"], h), Paragraph(t["s5"], p),
         Paragraph(t["ref_t"], h)] + [Paragraph(r, ref) for r in REFERENCIAS]

    def marco(canvas, d):
        canvas.saveState()
        canvas.setFont("Sans", 7.5)
        canvas.setFillColor(GRIS)
        canvas.drawString(d.leftMargin, letter[1] - 1.0 * cm, t["pie"])
        canvas.drawRightString(letter[0] - d.rightMargin, 0.9 * cm, t["pagina"].format(d.page))
        canvas.restoreState()

    doc.build(s, onFirstPage=marco, onLaterPages=marco)
    conteo = {k: palabras(t[k]) for k in ("resumen", "s1", "s2", "s3", "s4", "s5")}
    return salida, doc.page, conteo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--contacto", default="", help="correo de contacto del equipo (no se guarda en el repositorio)")
    a = ap.parse_args()
    registrar()
    for idioma in ("es", "en"):
        salida, paginas, conteo = construir(idioma, a.contacto)
        print(idioma, salida.name, "páginas:", paginas, "palabras:", conteo, "total:", sum(conteo.values()))


if __name__ == "__main__":
    main()
