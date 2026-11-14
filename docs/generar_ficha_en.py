"""
English technical sheet (PDF, max. 2 pages), built from the evaluation results in evaluacion/resultados/.

Usage (from the eco folder):
  python -m docs.generar_ficha_en --team "Team name" --members "A, B, C"
Output: docs/ECO_technical_sheet_EN.pdf
"""

import argparse

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from docs.generar_ficha import RAIZ, cargar, exactitud, global_de, pct, registrar_fuentes

TINTA = colors.HexColor("#1B1F1C")
GRAFITO = colors.HexColor("#33403A")
ACENTO = colors.HexColor("#2F7A5A")
SUAVE = colors.HexColor("#E8F2EC")
LINEA = colors.HexColor("#CFDDD5")
GRIS = colors.HexColor("#5F6B65")

TYPES = [("organico", "Organic coverage (4–5 real sources)"), ("literal", "Literal copies"),
         ("parafrasis", "Paraphrases, no new facts"), ("comunicado", "Replicated press release"),
         ("fabricado_literal", "Attack: copy + invented facts"), ("fabricado_parafrasis", "Attack: paraphrase + invented facts")]
MAIN = [t for t, _ in TYPES[:4]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", default="ECO TRACE Team")
    ap.add_argument("--members", default="Sadid Romero, Juan Felipe Jimenez, Ana Maria Vargas")
    ap.add_argument("--repo", default="https://github.com/SadidRomero77/eco")
    ap.add_argument("--web", default="https://eco.kibosecondbrain.com")
    ap.add_argument("--out", default=None, help="nombre del PDF de salida dentro de docs/")
    a = ap.parse_args()

    dev = cargar("comparacion_claudecode_sonnet.json")["resumenes"]
    test = cargar("comparacion_claudecode_sonnet__prueba.json")["resumenes"]
    agent = cargar("agente_claudecode_haiku.json")
    prov = cargar("procedencia_claudecode_sonnet.json")
    voice = cargar("voz_aasist.json")

    N, B = registrar_fuentes()
    title = ParagraphStyle("t", fontName=B, fontSize=15, leading=18, textColor=TINTA)
    sub = ParagraphStyle("s", fontName=N, fontSize=8.3, leading=10.5, textColor=GRIS, spaceAfter=3)
    h = ParagraphStyle("h", fontName=B, fontSize=10, leading=12, textColor=ACENTO, spaceBefore=5, spaceAfter=2)
    p = ParagraphStyle("p", fontName=N, fontSize=8.2, leading=10.4, textColor=GRAFITO, spaceAfter=2)
    cell = ParagraphStyle("c", fontName=N, fontSize=7.6, leading=9.2, textColor=GRAFITO)
    cellb = ParagraphStyle("cb", parent=cell, fontName=B, textColor=TINTA)
    head = ParagraphStyle("ch", parent=cell, fontName=B, textColor=colors.white)

    def table(rows, widths, bold_last=0):
        data = [[Paragraph(c, head) for c in rows[0]]]
        for i, r in enumerate(rows[1:], start=1):
            st = cellb if i > len(rows) - 1 - bold_last else cell
            data.append([Paragraph(c, cellb if j == 0 else st) for j, c in enumerate(r)])
        t = Table(data, colWidths=widths)
        style = [("BACKGROUND", (0, 0), (-1, 0), GRAFITO), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                 ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINEA), ("TOPPADDING", (0, 0), (-1, -1), 2),
                 ("BOTTOMPADDING", (0, 0), (-1, -1), 2), ("LEFTPADDING", (0, 0), (-1, -1), 4)]
        style += [("BACKGROUND", (0, i), (-1, i), SUAVE) for i in range(2, len(data), 2)]
        t.setStyle(TableStyle(style))
        return t

    s = []
    s.append(Paragraph("ECO — How many real sources are behind what reaches you?", title))
    s.append(Paragraph(f"Technical sheet · Track 4: Epistemic defense · {a.team}" + (f" · {a.members}" if a.members else "")
                       + f" · Live: {a.web} (MCP: {a.web}/mcp) · Code: {a.repo}", sub))

    s.append(Paragraph("1. Threat", h))
    s.append(Paragraph(
        "Generative AI makes it almost free to clone a story across dozens of sites and paraphrase it so it does not look "
        "copied, to fake photos with false dates or authorship, and to clone a voice for a forwarded WhatsApp voice note. "
        "People and web-searching AI agents read repetition as corroboration: five similar pages look like five sources "
        "(<b>source laundering</b>), and an agent passes that false confirmation on. Compression on messaging apps strips "
        "provenance metadata and degrades deepfake detectors exactly where rumors travel.", p))

    s.append(Paragraph("2. Defense: one engine, three questions, plain-language verdicts", h))
    s.append(Paragraph(
        "<b>(a) How many real sources?</b> One LLM call per set of pages extracts atomic, verifiable facts and aligns them "
        "across pages (paraphrases count as one fact; statements <i>about</i> the news, such as \"it is trending\", are "
        "excluded). An auditable, LLM-free rule walks pages chronologically: a page is an independent source only if it adds "
        "at least one fact nobody published before; a hybrid guard (char TF-IDF cosine ≥ 0.6) marks near-identical text as a "
        "copy. <b>(b) Where does this photo/video come from, and did an AI make it?</b> C2PA content credentials (c2pa-python) "
        "give signer, signed date, edits and declared AI origin. A signed date is a lower bound for the page that uses the "
        "photo (a backdated copy cannot pose as the origin), and reusing a photo signed by another outlet that published "
        "earlier implies dependence, even after re-compression (perceptual dHash). Also: AI markers in metadata (IPTC "
        "DigitalSourceType, EXIF, Stable Diffusion/ComfyUI PNG text, video tags) and experimental CV forensics (ELA, noise "
        "residual, FFT). <b>(c) Is this voice real?</b> AASIST-L retrained with WhatsApp-like Opus compression. "
        "<b>(d) WhatsApp inputs:</b> a voice note (Whisper transcription) or a screenshot (read by Claude vision) becomes a "
        "claim plus manipulation cues (urgency, \"forward this\", vague source) that a <b>live agent</b> investigates with a "
        "news search API (Exa), streaming every step and an interactive provenance graph. Every result opens with a "
        "traffic-light verdict and \"what to do\". Delivered as a bilingual web app, a Chrome extension (page, right-click on "
        "images, voice note, tab capture) and an MCP server (stdio + HTTP, 6 tools), deployed on AWS (Bedrock Claude) behind "
        "Cloudflare with per-IP rate limits, a daily LLM cap and SSRF protection.", p))

    s.append(Paragraph("3. Architecture", h))
    from docs.arquitectura import diagrama
    s.append(diagrama(18.6 * cm, N, B, "en"))
    s.append(Paragraph("Every entry point converges on one claim and one evidence engine; the same engine serves people (web, "
                       "extension) and agents (MCP). The LLM only extracts facts and reads media; the independence decision is "
                       "a deterministic, auditable rule.", p))

    s.append(Paragraph("4. Evaluation design", h))
    s.append(Paragraph(
        "Synthetic mini-internet with known ground truth (all outlets fictitious): <b>development</b> 36 worlds (6 events) "
        "used to design and tune ECO; <b>held-out test</b> 18 worlds from 3 new events, written after the last tuning and "
        "evaluated once; <b>provenance</b> 12 worlds with photos signed by a demo CA. Extractor: Claude Sonnet, blind (no "
        "tools, empty working directory). Baseline: text similarity + links. Voice: In-the-Wild (public, CC-BY-SA) with a "
        "<b>speaker-disjoint split</b> (train 37 speakers, test 17 speakers, 600 real + 600 fake test clips), Opus at 16 kbps "
        "(voice note) and 8 kbps (bad network); metric: equal error rate (EER).", p))

    s.append(Paragraph("5. Results", h))
    rows = [["World type (exact count of independent sources)", "Baseline (dev)", "ECO (dev)", "Baseline (held-out)", "ECO (held-out)"]]
    for t, label in TYPES:
        rows.append([label, pct(exactitud(dev, "linea_base", t)), pct(exactitud(dev, "hibrido", t)),
                     pct(exactitud(test, "linea_base", t)), pct(exactitud(test, "hibrido", t))])
    rows.append(["Main set overall", pct(global_de(dev, "linea_base", MAIN)), pct(global_de(dev, "hibrido", MAIN)),
                 pct(global_de(test, "linea_base", MAIN)), pct(global_de(test, "hibrido", MAIN))])
    s.append(table(rows, [7.1 * cm, 2.4 * cm, 2.2 * cm, 2.9 * cm, 2.7 * cm], bold_last=1))
    s.append(Spacer(1, 2))
    s.append(Paragraph(
        "No similarity threshold gets organic coverage and paraphrases right at once; fact-based ECO does, with 0 % false "
        "merging of independent outlets. <b>Honesty note:</b> the prompt was tuned twice on development errors, so the dev "
        "100 % is overfit; the number to report is the held-out one (n = 3 per type, one world = 33 points). A 7B local "
        "model falls below the baseline: extractor quality matters.", p))
    if agent:
        one = [f for f in agent if f["esperado"] == "una_sola_fuente"]
        org = [f for f in agent if f["esperado"] != "una_sola_fuente"]
        rate = lambda sub_, mode, lvl: sum(f[mode] == lvl for f in sub_) / max(len(sub_), 1)  # noqa: E731
        s.append(Paragraph(
            f"<b>Agent (Claude Haiku, 54 worlds):</b> with a single origin, it said \"confirmed by several sources\" "
            f"{pct(rate(one, 'sin_eco', 'confirmado_por_varias_fuentes'))} of the time without ECO and "
            f"{pct(rate(one, 'con_eco', 'confirmado_por_varias_fuentes'))} with ECO's report; it recognized the single origin "
            f"{pct(rate(one, 'sin_eco', 'una_sola_fuente'))} → {pct(rate(one, 'con_eco', 'una_sola_fuente'))}. Cost: on organic "
            f"coverage it recognized independence {pct(rate(org, 'sin_eco', 'confirmado_por_varias_fuentes'))} → "
            f"{pct(rate(org, 'con_eco', 'confirmado_por_varias_fuentes'))}.", p))
    if prov:
        r = prov["resumenes"]
        cel = lambda m, t: pct(r[m][t]["exactitud"]) + (f" (origin {pct(r[m][t]['origen_ok'])})" if t == "fecha_falsa" else "")  # noqa: E731
        rows_p = [["Provenance worlds (3 per type)", "Baseline", "ECO text only", "ECO + C2PA"]]
        for t, label in [("foto_firmada_parafrasis", "Rewritten copies with invented facts reusing the signed photo"),
                         ("foto_sin_metadatos", "Same, photo re-compressed without metadata (dHash)"),
                         ("fecha_falsa", "A copy backdated before the origin"),
                         ("organico_con_fotos", "Organic coverage (own photos, agency photo, AI image, broken signature)")]:
            rows_p.append([label, cel("linea_base", t), cel("eco_sin_procedencia", t), cel("eco_con_procedencia", t)])
        s.append(Spacer(1, 3))
        s.append(table(rows_p, [8.4 * cm, 2.6 * cm, 3.0 * cm, 3.3 * cm]))
        s.append(Paragraph("Provenance closes the open text-only attack <i>when copies reuse the signed photo</i>. Worlds and "
                           "rule were designed together (not held out). Declared-AI images and broken signatures were flagged "
                           "in all 3 worlds where they appear.", p))
    if voice:
        conds = [("limpio", "Clean"), ("opus_16k", "Opus 16 kbps (voice note)"), ("opus_8k", "Opus 8 kbps")]
        names = {"AASIST-L preentrenado": "AASIST-L, off the shelf", "AASIST preentrenado": "AASIST, off the shelf",
                 "AASIST-L reentrenado (solo limpio)": "AASIST-L retrained, clean only (control)",
                 "AASIST-L reentrenado (con códec)": "AASIST-L retrained with codec augmentation (deployed)"}
        rows_v = [["Voice detector · EER on In-the-Wild (lower is better)"] + [c for _, c in conds]]
        for k, v in voice["modelos"].items():
            rows_v.append([names.get(k, k)] + [f"{v[c]['eer'] * 100:.1f} %" for c, _ in conds])
        s.append(Spacer(1, 3))
        s.append(table(rows_v, [7.9 * cm, 2.6 * cm, 4.0 * cm, 2.8 * cm]))
        s.append(Paragraph(
            "Lab-trained detectors behave like chance on real-world voices. Retraining halves the error; codec augmentation "
            "makes it nearly flat under compression (+1.7 points clean→8 kbps vs +9.0 for the control) at a small cost on "
            "clean audio. Shown to users as \"probably real / probably synthetic\" with its error rate, never as proof.", p))

    s.append(Paragraph("6. Live test on real news (public server)", h))
    s.append(Paragraph(
        "Topic <i>\"FAA nationwide ground stop in the US\"</i> (last 7 days): the agent found 10 articles (FAA statement, El País, "
        "BBC, AP, CNN en Español, Telemundo, Infobae, Bloomberg Línea…), Claude Sonnet 4.6 extracted 47 facts in about 30 s, and "
        "the rule returned <b>10 pages → 9 independent sources</b>, with the FAA statement as the original source and one AP "
        "piece flagged as repeating BBC. A synthetic Spanish voice note (\"urgent, forward to everyone… my cousin at the water "
        "utility says…\") was transcribed, reduced to a checkable claim with three manipulation cues (urgency, forward request, "
        "vague source) and its voice was flagged <b>probably synthetic</b>. What a person sees first is one sentence, e.g. "
        "<i>\"(red light) One single source behind everything: the 5 pages repeat what X published. Many websites saying it does not "
        "make it more reliable.\"</i>", p))

    s.append(Paragraph("7. Limits", h))
    s.append(Paragraph(
        "<b>ECO measures independence and provenance, not truth</b>: several independent sources can be wrong. "
        "<b>Open attack (text only):</b> rewritten copies that invent different details per page count as independent; "
        "provenance stops it only if the photo is reused. <b>C2PA</b> proves who signed, not what is true; absence of a "
        "signature means nothing (most content has none); here the trust list is a demo CA and the signed date is "
        "signer-declared (production: official C2PA trust list + RFC 3161 timestamps). <b>Chronology</b> trusts publication "
        "dates (wire agencies published later may look like copies). <b>Voice</b> evaluated in English on public figures. "
        "<b>CV forensics</b> are experimental and not evaluated. Synthetic benchmark, small n.", p))

    s.append(Paragraph("8. Dual-use risk and mitigations", h))
    s.append(Paragraph(
        "An attacker could use ECO or the voice detector as an oracle to polish copies or clones until they pass. Mitigations: "
        "per-IP rate limits and a daily LLM cap on the public server, no published production thresholds, and priority to "
        "signals the attacker does not control (third-party C2PA signatures, domain history). Verdicts are framed as alerts to "
        "verify through another channel, never to accuse a person. The benchmark is fictitious and labeled synthetic; no "
        "third-party systems were tested.", p))

    s.append(Paragraph("9. Reproducibility and credits", h))
    s.append(Paragraph(
        "<font face='Courier'>python -m pruebas.prueba_humo · python -m evaluacion.evaluar --modelo claudecode/sonnet "
        "[--conjunto prueba] · python -m evaluacion.evaluar_procedencia · python deteccion_voz/experimento.py</font>. All "
        "results, version history and cached LLM answers are in the repository. Code written with the assistance of Claude "
        "(Anthropic), declared as AI-generated material. Data: synthetic corpus; In-the-Wild (CC-BY-SA 4.0); AASIST (MIT, "
        "NAVER). Stack: FastAPI, MCP SDK, c2pa-python, PyTorch, faster-whisper, Amazon Bedrock, Exa, Cloudflare.", p))

    out = RAIZ / "docs" / (a.out or "ECO_technical_sheet_EN.pdf")
    SimpleDocTemplate(str(out), pagesize=letter, leftMargin=1.45 * cm, rightMargin=1.45 * cm, topMargin=1.1 * cm,
                      bottomMargin=1.0 * cm, title="ECO — Technical sheet").build(s)
    from pypdf import PdfReader
    n = len(PdfReader(str(out)).pages)
    print(f"Technical sheet: {out} ({n} page{'s' if n != 1 else ''})")
    if n > 2:
        print("WARNING: more than 2 pages.")


if __name__ == "__main__":
    main()
