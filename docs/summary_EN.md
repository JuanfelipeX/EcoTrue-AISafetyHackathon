# ECO — How many real sources are behind what reaches you?

**Track 4 · Epistemic defense** · Live: <https://eco.kibosecondbrain.com> · MCP: `https://eco.kibosecondbrain.com/mcp` ·
Code: <https://github.com/SadidRomero77/eco>

## The problem

Generative AI has driven the cost of manufacturing *apparent* evidence close to zero. A single claim can be cloned across
dozens of websites and paraphrased so each copy looks original; a photo can be reused with a false date or attributed to
someone else; a voice can be cloned and forwarded as a WhatsApp voice note. People — and, increasingly, AI agents with web
search — treat repetition as corroboration: five similar pages read as five sources, and an agent confidently reports
"several sources confirm it". We call this **source laundering**. It is especially damaging in Latin America, where
rumors travel as forwarded audios and screenshots and messaging apps strip the metadata that could reveal their origin.

## What ECO is

ECO is an epistemic-defense engine that answers three questions in plain language, for technical and non-technical users
alike:

1. **How many real sources are behind this claim?**
2. **Where does this photo or video come from, and was it made with AI?**
3. **Is this voice real?**

ECO does not tell people what is true. It shows how much *independent* evidence supports a claim, where it originated
and who copied whom — and every result opens with a one-sentence, traffic-light verdict plus "what to do" (e.g.
*"One single source behind everything: the 5 pages repeat what X published. Many websites saying it does not make it
more reliable."*). Technical detail is one click away.

## How it works

**Source independence (text).** One LLM call per set of pages extracts atomic, verifiable facts (figures, places,
testimonies) and aligns them across pages, so two paraphrases of the same fact count once. Statements *about* the news
("it is trending", "shared on social media") are excluded so a copy cannot look original by adding them. Then an
auditable, LLM-free rule walks the pages in chronological order: a page is an independent source only if it contributes
at least one fact nobody had published before. A hybrid guard marks near-identical text (character TF-IDF cosine ≥ 0.6)
as a copy even if it adds invented details. The output: apparent vs. independent sources, the origin of each cluster,
an origin tree, and which facts are corroborated by two or more independent sources versus resting on one.

**Cryptographic provenance (C2PA) and AI markers.** ECO verifies Content Credentials (via `c2pa-python`) on images and
videos: signer, signed date, edit history, declared AI origin, and whether the file was altered after signing. Provenance
feeds back into the source analysis in two ways: a signed date is a lower bound for the page that uses the photo (a copy
cannot backdate itself before the origin), and a page that uses a photo signed by another outlet that published earlier —
with no signed photo of its own — depends on that outlet. The same photo stripped of metadata (e.g. re-compressed when
forwarded) is still recognized through a perceptual hash. ECO also reads AI markers left in metadata (IPTC
DigitalSourceType, EXIF software tags, Stable Diffusion/ComfyUI PNG parameters, video tags) and shows experimental
computer-vision forensics (error level analysis, noise residual, frequency spectrum) as visual hints, never as verdicts.

**Synthetic-voice detection.** Audio is first checked for C2PA credentials; if there are none (WhatsApp never keeps them),
an AASIST-L anti-spoofing model retrained by us with WhatsApp-like Opus compression estimates whether the voice is
synthetic, and reports its own error rate.

**WhatsApp inputs and a live agent.** A voice note is transcribed with Whisper on the server; a screenshot (a tweet, a
headline, a forwarded message) is read by Claude vision. ECO extracts the central checkable claim and manipulation cues
(urgency, "forward this", vague sources such as "my cousin who works there"), checks the voice or the image, and then a
**live agent** investigates the claim: it searches recent news through the Exa search API, reads each article, extracts
facts and decides outlet by outlet — streaming every step to the user, ending with an interactive provenance graph and
sources ranked by evidence (original reporting first), not by reputation — topped by a **recommended source to read
first**, with its reasons: the official/primary source if present, otherwise the outlet whose own facts are most
confirmed by other independent outlets (a signed photo of its own counts in its favor). It rewards original reporting
and demotes copies without blacklisting anyone.

## Delivery and deployment

- **Bilingual web app (ES/EN)** with three entry points (topic or URL, voice note, image or screenshot), a lab with the
  benchmark, results, installation guides and shareable reports.
- **Chrome extension** (works in Chrome, Edge, Brave, Opera): analyze the current article, right-click any image or
  selected text, upload a voice note, or capture the current tab — with the same live agent and graph in the popup.
- **MCP server** (stdio and Streamable HTTP, no install needed) with six tools: `evaluar_corroboracion`,
  `investigar_tema`, `verificar_procedencia`, `evaluar_audio`, `buscar_en_mini_internet`, `analizar_mundo`, so any agent
  (Claude, Cursor, VS Code) can check corroboration *before* claiming it.
- **Production deployment** on AWS (EC2 + Docker + Caddy) behind Cloudflare, Claude via Amazon Bedrock (IAM role, no
  keys on disk), secrets in SSM, per-IP rate limiting, a daily LLM cap and SSRF protection for user-supplied URLs.

## Evaluation and results

All benchmark content is synthetic and labeled as such (fictitious outlets, people and places); every world has a known
ground truth stored apart from the analysis. The extractor (Claude Sonnet) ran blind, with no tools and an empty working
directory.

**Source independence.** On the **held-out test set** (18 worlds from 3 new events, written after the last tuning and
evaluated once), ECO counted independent sources exactly in **92 %** of the main worlds versus **83 %** for a text-similarity
baseline; the gain comes from paraphrases (67 % vs 33 %), and ECO never merged independent outlets (0 % false merging). No
similarity threshold gets both organic coverage and paraphrases right. We report honestly that the prompt was tuned twice
on development errors, so the 100 % development score is overfit; the held-out number is the one that counts (n = 3 per
type).

**Agent behavior.** With the same pages, an agent (Claude Haiku, 54 worlds) said "confirmed by several sources" when there
was a single origin **51 %** of the time without ECO and **22 %** with ECO's report; it recognized the single origin
42 % → 78 %. The cost: on genuinely independent coverage it recognized independence 100 % → 89 %.

**Provenance.** In 12 worlds with signed photos, the attack that text alone cannot stop — rewritten copies that invent
details — went from **0 % to 100 %** detection when copies reuse the origin's signed photo, also **0 % → 100 %** when the
photo was re-compressed without metadata, and backdated copies were caught in every case (correct origin 33 % → 100 %),
with no false merging of independent coverage. Declared-AI images and broken signatures were flagged in all worlds where
they appear. (These worlds and the rule were designed together: this shows the mechanism works, not a held-out score.)

**Voice.** On In-the-Wild (public dataset of real and deepfaked voices of public figures; speaker-disjoint split, 600 real
+ 600 fake test clips from 17 unseen speakers), off-the-shelf detectors performed like chance: **AASIST-L 48.5 % EER**
(49.7 % with voice-note compression, 55.7 % on a bad network). Retraining on real-world audio halved the error (control:
24.7 / 25.8 / 33.7 %), and our codec-augmented model is nearly flat under compression: **28.8 / 28.7 / 30.5 %** (+1.7
points from clean to 8 kbps, versus +9.0 for the control). It is shown to users as "probably real / probably synthetic"
with its error rate.

**Real-world test.** On the topic "FAA nationwide ground stop" the live agent found 10 articles (including the FAA's own
statement, BBC, AP, CNN en Español, El País, Infobae), extracted 47 facts in about 30 seconds and returned 9 independent
sources, identifying the FAA statement as the original and one wire piece as a repetition.

## Honest limitations

- **Independence is not truth**: several independent sources can be wrong together.
- **Text-only open attack**: copies that are rewritten *and* invent different details per page still look independent;
  provenance closes it only when the photo is reused.
- **C2PA** proves who signed, not what is true; most content carries no signature, so its absence means nothing. Our trust
  list is a demo CA and the signed date is signer-declared (production: the official C2PA trust list and RFC 3161
  timestamps).
- **Chronology** trusts publication dates: a wire agency published later can look like a copy.
- **Voice** was evaluated in English on public figures; Spanish WhatsApp audio is the target but not yet measured. CV
  forensics are experimental and unevaluated. The benchmark is synthetic with small n.

## Dual use

An attacker could use ECO or the voice detector as an oracle to polish copies or clones until they pass. Mitigations:
per-IP rate limits and a daily cap on the public server, no published production thresholds, and priority to signals
the attacker cannot forge (third-party cryptographic signatures). Verdicts are framed as prompts to verify through
another channel — never as grounds to accuse a person.

## Why it matters

Fact-checking cannot scale to the volume of AI-generated content, but **independence of sources** can be measured
automatically, and it is exactly what source laundering attacks. ECO turns that measurement into something a grandmother
receiving a forwarded audio, a journalist and an AI agent can all use — and it is already live.

*Code written with the assistance of Claude (Anthropic) and declared as AI-generated material. Data: synthetic corpus;
In-the-Wild (CC-BY-SA 4.0); AASIST (MIT, NAVER).*
