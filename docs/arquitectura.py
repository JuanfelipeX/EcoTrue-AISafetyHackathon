"""Diagrama de arquitectura de ECO para las fichas técnicas (ReportLab, vectorial). idioma: "en" | "es"."""

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors

VERDE = colors.HexColor("#2F7A5A")
VERDE_SUAVE = colors.HexColor("#E8F2EC")
GRIS = colors.HexColor("#5F6B65")
TINTA = colors.HexColor("#1B1F1C")
BORDE = colors.HexColor("#B9CCC1")
FONDO = colors.HexColor("#F6F8F7")

TEXTOS = {
    "en": {
        "entradas": "INPUTS", "ingesta": "INGESTION", "motor": "ECO ENGINE", "salidas": "OUTPUTS",
        "e": ["News article / URLs", "Topic or claim", "WhatsApp voice note", "Screenshot, photo, video"],
        "i": ["Safe fetcher (SSRF guard)", "Exa news search API", "Whisper transcription", "Claude vision (reads text)"],
        "m": ["1  Atomic facts · Claude (Bedrock)", "2  Chronological rule (no LLM)", "    + hybrid copy guard",
              "3  C2PA · dHash · AI marks", "4  Voice: AASIST-L (codec-aug.)", "5  Plain-language verdict"],
        "s": ["Web app ES/EN + live agent", "Chrome extension", "MCP server · 6 tools", "Shareable report"],
        "infra": "AWS EC2 · Docker · Caddy · Cloudflare  |  Bedrock via IAM role · secrets in SSM · per-IP rate limit · daily LLM cap",
    },
    "es": {
        "entradas": "ENTRADAS", "ingesta": "INGESTA", "motor": "MOTOR ECO", "salidas": "SALIDAS",
        "e": ["Noticia / URLs", "Tema o afirmación", "Nota de voz de WhatsApp", "Captura, foto, video"],
        "i": ["Descarga segura (anti-SSRF)", "Buscador de noticias Exa", "Transcripción Whisper", "Claude visión (lee texto)"],
        "m": ["1  Hechos atómicos · Claude", "2  Regla cronológica (sin LLM)", "    + guardia de copias",
              "3  C2PA · dHash · marcas de IA", "4  Voz: AASIST-L (con códec)", "5  Conclusión en lenguaje sencillo"],
        "s": ["Web ES/EN + agente en vivo", "Extensión de Chrome", "Servidor MCP · 6 herramientas", "Informe para compartir"],
        "infra": "AWS EC2 · Docker · Caddy · Cloudflare  |  Bedrock con rol IAM · secretos en SSM · límite por IP · tope diario del LLM",
    },
}


def _caja(d, x, y, w, h, texto, fuente, tam=6.9, relleno=colors.white, borde=BORDE, color=TINTA, negrita=None):
    d.add(Rect(x, y, w, h, rx=4, ry=4, fillColor=relleno, strokeColor=borde, strokeWidth=0.7))
    d.add(String(x + 5, y + h / 2 - tam / 3, texto, fontName=negrita or fuente, fontSize=tam, fillColor=color))


def _flecha(d, x1, y1, x2, y2):
    d.add(Line(x1, y1, x2, y2, strokeColor=GRIS, strokeWidth=0.8))
    d.add(Polygon([x2, y2, x2 - 4.5, y2 + 2.4, x2 - 4.5, y2 - 2.4], fillColor=GRIS, strokeColor=GRIS, strokeWidth=0))


def diagrama(ancho, fuente, negrita, idioma="en"):
    t = TEXTOS[idioma]
    alto = 150
    d = Drawing(ancho, alto)
    d.add(Rect(0, 0, ancho, alto, rx=6, ry=6, fillColor=FONDO, strokeColor=None))
    # columnas
    m = 6
    sep = 14
    c1, c2, c4 = 98, 108, 112
    c3 = ancho - (c1 + c2 + c4) - m * 2 - 3 * sep
    x1, x2 = m, m + c1 + sep
    x3 = x2 + c2 + sep
    x4 = x3 + c3 + sep
    y_top, h, g = alto - 26, 18, 6
    for x, titulo in ((x1, t["entradas"]), (x2, t["ingesta"]), (x3, t["motor"]), (x4, t["salidas"])):
        d.add(String(x + 2, alto - 13, titulo, fontName=negrita, fontSize=7.2, fillColor=VERDE))
    filas = [y_top - i * (h + g) - h for i in range(4)]
    for i in range(4):
        _caja(d, x1, filas[i], c1, h, t["e"][i], fuente)
        _caja(d, x2, filas[i], c2, h, t["i"][i], fuente)
        _caja(d, x4, filas[i], c4, h, t["s"][i], fuente, relleno=VERDE_SUAVE, borde=VERDE)
        _flecha(d, x1 + c1 + 2, filas[i] + h / 2, x2 - 2, filas[i] + h / 2)
    # motor: un bloque con sus capas
    y_m0, y_m1 = filas[3], y_top
    d.add(Rect(x3, y_m0, c3, y_m1 - y_m0, rx=5, ry=5, fillColor=colors.white, strokeColor=VERDE, strokeWidth=1.3))
    paso = (y_m1 - y_m0 - 8) / len(t["m"])
    for i, linea in enumerate(t["m"]):
        d.add(String(x3 + 7, y_m1 - 12 - i * paso, linea, fontName=negrita if linea[:1].isdigit() else fuente,
                     fontSize=6.9, fillColor=TINTA))
    for i in range(4):
        _flecha(d, x2 + c2 + 2, filas[i] + h / 2, x3 - 2, filas[i] + h / 2)
        _flecha(d, x3 + c3 + 2, filas[i] + h / 2, x4 - 2, filas[i] + h / 2)
    # infraestructura
    d.add(Rect(m, 6, ancho - 2 * m, 16, rx=4, ry=4, fillColor=GRIS, strokeColor=None))
    d.add(String(m + 6, 11, t["infra"], fontName=fuente, fontSize=6.9, fillColor=colors.white))
    return d
