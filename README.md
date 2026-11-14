# ECO — ¿Cuántas fuentes hay de verdad detrás de una afirmación?

Hackathon Def/Acc (AI Safety Colombia × IEEE CS Uniandes) · Frente 4: Defensa epistémica.

Con IA es casi gratis clonar una afirmación en decenas de sitios y parafrasearla para que no parezca copia.
Las personas y los agentes con búsqueda web cuentan esa repetición como corroboración.
ECO detecta cuándo muchas páginas vienen en realidad de un solo origen. No dice si algo es verdad:
dice cuánta evidencia independiente lo respalda.

| Pieza | Para quién | Dónde |
|---|---|---|
| Panel web (laboratorio, resultados, URLs propias) | Jurado, investigadores | `web/` → `http://localhost:8765/` |
| Extensión de Chrome | Personas que leen noticias | `extension/` |
| Servidor MCP | Agentes (Claude Desktop, Claude Code, otros clientes MCP) | `mcp_eco/` |
| API + mini-internet sintético + benchmark | Demo, pruebas y evaluación | `api/`, `corpus/`, `evaluacion/` |

## Cómo funciona

1. **Hechos atómicos.** Un LLM lee todas las páginas y lista los datos verificables, marcando en qué páginas
   aparece cada uno. Dos redacciones del mismo dato son el mismo hecho: la paráfrasis no engaña. También separa
   las frases *sobre la noticia* (quién la informó, que es tendencia) de los datos *sobre el suceso*.
2. **Regla de independencia** (sin LLM, auditable). En orden cronológico, una página es fuente independiente
   solo si aporta al menos un dato que nadie había publicado antes.
3. **Guardia híbrida.** Si el texto es casi idéntico a una página anterior, cuenta como copia aunque agregue datos.
4. **Qué se puede demostrar.** Para cada dato se cuenta cuántas fuentes independientes lo respaldan.

## Instalación

```bash
python -m venv .venv
.venv\Scripts\activate                # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                # macOS/Linux: cp .env.example .env
python -m pruebas.prueba_humo         # todo en OK, sin gastar API (usa respuestas guardadas)
```

### Modelos (`.env`)

`LLM_MODELO` y `LLM_MODELOS_RESPALDO` aceptan `proveedor/modelo`. Si uno falla se prueba el siguiente,
y toda respuesta queda en caché en `.cache/llm/` (auditable y útil sin conexión).

| Proveedor | Ejemplo | Requiere |
|---|---|---|
| `claudecode` | `claudecode/sonnet`, `claudecode/haiku` | La CLI de Claude Code con sesión iniciada. Corre sin herramientas y desde una carpeta vacía: el modelo no ve el proyecto. |
| `openrouter` | `openrouter/anthropic/claude-sonnet-5.5` | `OPENROUTER_API_KEY` **de inferencia** (`sk-or-v1-…`). Una clave de gestión responde `401 User not found`. |
| `anthropic` | `anthropic/claude-haiku-5-5` | `ANTHROPIC_API_KEY` |
| `openai` | `openai/gpt-5.6-luna` | `OPENAI_API_KEY` |
| `ollama` | `ollama/qwen2.5:7b` | Ollama local. Sin clave ni costo, pero un modelo de 7B rinde por debajo de la línea base. |
| `manual` | `manual/claude-opus-5-5-sesion` | Respuestas escritas durante el desarrollo (histórico). |

## Uso

```bash
python -m scripts.demo                       # servidor en :8765 + Chrome con la extensión ya instalada
uvicorn api.servidor:app --port 8765         # solo el servidor (panel en /, mini-internet en /internet, API en /docs)
python -m scripts.config_mcp --instalar      # registra el MCP en Claude Desktop y Claude Code
python -m scripts.probar_mcp                 # prueba el MCP por stdio, como lo haría un cliente
python -m evaluacion.evaluar --modelo claudecode/sonnet                     # conjunto de desarrollo
python -m evaluacion.evaluar --modelo claudecode/sonnet --conjunto prueba   # conjunto retenido
python -m demo.agente --modelo claudecode/haiku --conjunto todos            # agente sin ECO vs. con ECO
python -m docs.generar_ficha --equipo "…" --integrantes "…" --repo "…"     # ficha técnica (2 páginas)
```

**Extensión en el Chrome personal:** `chrome://extensions` → Modo de desarrollador → Cargar descomprimida → `extension/`.
Clic derecho en una página del mini-internet → *ECO: ¿cuántas fuentes reales hay detrás de esto?*. El servidor se
cambia en el popup → «Servidor de ECO». (`python -m scripts.demo` usa Chrome for Testing porque el Chrome normal ya no
acepta `--load-extension`.)

**MCP:** herramientas `evaluar_corroboracion(afirmacion, urls)`, `buscar_en_mini_internet(consulta)` y `analizar_mundo(mundo_id)`.
Ejemplo en Claude: *"¿Es cierto que el acueducto de San Aurelio suspendió el agua por mercurio? Usa ECO con el mundo e01-s1."*

Guía de la demo y del pitch: [DEMO.md](DEMO.md). Resumen para el envío: [docs/resumen.md](docs/resumen.md).

## Mini-internet sintético (`corpus/`)

`python corpus/generar_corpus.py` crea 54 mundos (9 eventos ficticios) con 304 páginas.

| Conjunto | Mundos | Uso |
|---|---|---|
| desarrollo: principal | 24 (eventos e01–e06) | orgánico, copia literal, paráfrasis, comunicado |
| desarrollo: estrés | 12 (eventos e01–e06) | copias que inventan testimonios y cifras (literal y parafraseada) |
| **prueba retenida** | 18 (eventos e07–e09) | los 6 tipos; escritos después del último ajuste y evaluados una sola vez |

`ground_truth.json` guarda las respuestas; `indice_busqueda.json` solo temas y URLs (lo único que usa el buscador
simulado, así que la API nunca ve las respuestas). Todo el contenido es ficticio y cada página lo indica.

## Resultados (modelos reales, extracción a ciegas)

Exactitud del conteo de fuentes independientes. Extractor: Claude Sonnet vía Claude Code.

| Tipo | Línea base (des.) | ECO híbrido (des.) | Línea base (prueba) | ECO híbrido (prueba) |
|---|---|---|---|---|
| orgánico | 100 % | 100 % | 100 % | 100 % |
| copia literal | 100 % | 100 % | 100 % | 100 % |
| paráfrasis | 33 % | 100 % | 33 % | 67 % |
| comunicado | 100 % | 100 % | 100 % | 100 % |
| fabricado literal (ataque) | 100 % | 100 % | 100 % | 100 % |
| fabricado paráfrasis (ataque) | 0 % | 0 % | 0 % | 0 % |
| **global principal** | 83 % | 100 % | 83 % | **92 %** |
| **global estrés** | 50 % | 50 % | 50 % | 50 % |

- Fusión falsa de medios independientes: 0 % en todos los casos. Claude Haiku da las mismas cifras en el conjunto de prueba.
- Ningún umbral de la línea base acierta a la vez orgánico y paráfrasis (`python -m evaluacion.evaluar_linea_base --barrido`).
- **Agente** (Claude Haiku, 54 mundos): con un solo origen, dice «confirmado por varias fuentes» en el 51 % sin ECO y
  en el 22 % con ECO; reconoce el origen único 42 % → 78 %. Costo: en cobertura orgánica reconoce independencia 100 % → 89 %.
- **Modelo pequeño:** con `ollama/qwen2.5:7b` ECO queda por debajo de la línea base (67 % en la v1). La calidad del extractor manda.

**Advertencias honestas.**
- El prompt se ajustó dos veces mirando errores del conjunto de desarrollo (v1 → v3, ver `evaluacion/resultados/historial/`):
  v2 separa frases de atribución, v3 suma comentarios sobre la difusión y pide no partir un dato en sub-detalles.
  El 100 % de desarrollo está sobreajustado; la cifra a reportar es la del conjunto de prueba retenido (92 %, n = 3 por tipo).
- Las paráfrasis del corpus están escritas a mano; las de un LLM serían más variadas.
- Ataque no resuelto: reescribir el texto e inventar detalles nuevos en cada copia.

## Estructura

```
corpus/       generador y mini-internet sintético (desarrollo + prueba retenida)
motor/        config, cliente LLM agnóstico, extracción, línea base, hechos, buscador, análisis
api/          servidor FastAPI (panel + mini-internet + API)
web/          panel web (HTML/CSS/JS sin dependencias externas: funciona sin internet)
mcp_eco/      servidor MCP
extension/    extensión de Chrome (Manifest V3)
evaluacion/   evaluación, resultados e historial de versiones
demo/         agente sin ECO vs. con ECO
scripts/      demo, configuración y prueba del MCP, prueba de proveedores
pruebas/      prueba de humo
docs/         resumen para el envío y ficha técnica
```

## Uso responsable y créditos

Datos 100 % sintéticos: no se analizaron sitios reales de terceros. El código fue escrito con asistencia de
Claude (Anthropic) y se declara como material generado con IA. Las respuestas de los modelos usados en la
evaluación están en `.cache/llm/` para auditoría.
