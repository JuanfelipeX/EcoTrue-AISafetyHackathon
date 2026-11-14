# ECO — ¿Cuántas fuentes hay de verdad detrás de una afirmación?

Hackathon Def/Acc (AI Safety Colombia × IEEE CS Uniandes) · Frente 4: Defensa epistémica.

Con IA es casi gratis clonar una afirmación en decenas de sitios y parafrasearla para que no parezca copia.
Las personas y los agentes con búsqueda web cuentan esa repetición como corroboración.
ECO detecta cuándo muchas páginas vienen en realidad de un solo origen. No dice si algo es verdad:
dice cuánta evidencia independiente lo respalda.

**En línea:** <https://eco.kibosecondbrain.com> · MCP remoto: `https://eco.kibosecondbrain.com/mcp` ·
instrucciones para instalar la extensión y el MCP: <https://eco.kibosecondbrain.com/#instalar>

Tres capas de defensa epistémica, un mismo motor:

| Pregunta | Capa | Dónde |
|---|---|---|
| ¿Cuántas fuentes hay de verdad? | Independencia de fuentes (hechos atómicos + regla cronológica) | `motor/hechos.py` |
| ¿De dónde viene esta foto o video? ¿Lo hizo una IA? | Procedencia C2PA + huella visual + marcas de IA en metadatos (IPTC, EXIF, PNG de Stable Diffusion, etiquetas de video) | `motor/procedencia.py` |
| ¿Es real esta voz? | Detector AASIST-L reentrenado con audio tipo WhatsApp | `motor/voz.py`, `deteccion_voz/` |
| ¿Qué dice esta nota de voz o captura, y es cierto? | Whisper / Claude visión → afirmación → agente con buscador (Exa) | `motor/multimodal.py`, `motor/web_real.py` |

| Pieza | Para quién | Dónde |
|---|---|---|
| Panel web (laboratorio, resultados, URLs, imágenes, audio, instalar) | Jurado, investigadores, público | `web/` → `http://localhost:8765/` |
| Extensión de Chrome | Personas que leen noticias | `extension/` (descarga en `/descargas/eco-extension.zip`) |
| Servidor MCP (stdio y HTTP) | Agentes (Claude, Cursor, VS Code…) | `mcp_eco/` |
| API + mini-internet sintético + benchmark | Demo, pruebas y evaluación | `api/`, `corpus/`, `evaluacion/` |
| Despliegue en AWS (EC2 + Docker + Caddy, detrás de Cloudflare) | Acceso desde cualquier red | `Dockerfile`, `docker-compose.yml`, `despliegue/` |

## Cómo funciona

1. **Hechos atómicos.** Un LLM lee todas las páginas y lista los datos verificables, marcando en qué páginas
   aparece cada uno. Dos redacciones del mismo dato son el mismo hecho: la paráfrasis no engaña. También separa
   las frases *sobre la noticia* (quién la informó, que es tendencia) de los datos *sobre el suceso*.
2. **Regla de independencia** (sin LLM, auditable). En orden cronológico, una página es fuente independiente
   solo si aporta al menos un dato que nadie había publicado antes.
3. **Guardia híbrida.** Si el texto es casi idéntico a una página anterior, cuenta como copia aunque agregue datos.
4. **Qué se puede demostrar.** Para cada dato se cuenta cuántas fuentes independientes lo respaldan.
5. **Procedencia (C2PA).** Si las páginas traen fotos con credenciales de contenido, ECO las verifica. La fecha
   firmada de una foto es un límite inferior para la página que la usa (una copia no puede hacerse pasar por el
   origen con una fecha falsa), y usar la foto firmada por otro medio que publicó antes, sin foto propia, implica
   dependencia. La misma foto sin metadatos (recomprimida al reenviarla) se reconoce por su huella visual (dHash).
6. **Voz.** Un audio se revisa primero por C2PA; si no tiene firma, el detector AASIST-L estima si es sintético.

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

**MCP:** herramientas `evaluar_corroboracion(afirmacion, urls)`, `buscar_en_mini_internet(consulta)`, `analizar_mundo(mundo_id)`,
`verificar_procedencia(url_imagen)` y `evaluar_audio(url_audio)`. Remoto, sin instalar nada:
`claude mcp add --transport http eco https://eco.kibosecondbrain.com/mcp`.
Ejemplo en Claude: *"¿Es cierto que el acueducto de San Aurelio suspendió el agua por mercurio? Usa ECO con el mundo e01-s1."*

Guía de la demo y del pitch: [DEMO.md](DEMO.md). Resumen para el envío: [docs/resumen.md](docs/resumen.md).

## Mini-internet sintético (`corpus/`)

`python corpus/generar_corpus.py` crea 66 mundos (9 eventos ficticios) con 371 páginas.

| Conjunto | Mundos | Uso |
|---|---|---|
| desarrollo: principal | 24 (eventos e01–e06) | orgánico, copia literal, paráfrasis, comunicado |
| desarrollo: estrés | 12 (eventos e01–e06) | copias que inventan testimonios y cifras (literal y parafraseada) |
| **prueba retenida** | 18 (eventos e07–e09) | los 6 tipos; escritos después del último ajuste y evaluados una sola vez |
| procedencia (C2PA) | 12 (eventos e07–e09) | fotos firmadas por una CA de demostración (`corpus/c2pa/`): foto reutilizada, foto sin metadatos, fecha falsa, cobertura independiente con fotos de agencia, IA y una firma rota |

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
- Ataque no resuelto **solo con texto**: reescribir el texto e inventar detalles nuevos en cada copia (ver procedencia).

### Procedencia C2PA (`python -m evaluacion.evaluar_procedencia --modelo claudecode/sonnet`)

Mismos hechos extraídos; solo cambia si ECO usa la procedencia. 3 mundos por tipo.

| Mundo | Línea base | ECO solo texto | ECO + C2PA |
|---|---|---|---|
| copias reescritas con detalles inventados que reutilizan la foto firmada | 0 % | 0 % | **100 %** |
| lo mismo, con la foto recomprimida sin metadatos (huella visual) | 0 % | 0 % | **100 %** |
| una copia con fecha falsa anterior al origen (origen correcto) | 0 % (33 %) | 33 % (33 %) | **100 % (100 %)** |
| cobertura independiente con fotos propias, de agencia, IA y una firma rota | 100 % | 100 % | 100 % |

Las imágenes declaradas como IA y las firmas rotas se detectan en los 3 mundos donde aparecen. **Advertencia:** los
mundos y la regla se diseñaron juntos; muestra que el mecanismo funciona cuando el atacante reutiliza la foto firmada.
Si fabrica sus propias fotos sin firma, ECO solo puede decir «sin procedencia». C2PA prueba procedencia, no verdad, y
la lista de confianza aquí es una CA de demostración.

### Voz clonada (AASIST-L, In-the-Wild)

Partición por hablante (37 personas para reentrenar, 17 para probar; 600 audios reales y 600 falsos de prueba).
Opus a 16 kbps simula una nota de voz de WhatsApp y a 8 kbps una red mala. Tasa de error igual (EER, menor es mejor):

| Detector | Limpio | Opus 16 kbps | Opus 8 kbps |
|---|---|---|---|
| AASIST preentrenado (ASVspoof 2019) | 49,7 % | 54,2 % | 56,7 % |
| AASIST-L preentrenado | 48,5 % | 49,7 % | 55,7 % |
| AASIST-L reentrenado solo con audio limpio (control) | **24,7 %** | **25,8 %** | 33,7 % |
| AASIST-L reentrenado con aumento de códec (en producción) | 28,8 % | 28,7 % | **30,5 %** |

- Los detectores de laboratorio fallan como el azar con voces reales: no sirven tal como vienen.
- Reentrenar con audio real reduce el error a la mitad; el aumento de códec hace que casi no empeore al comprimir
  (+1,7 puntos de limpio a 8 kbps, frente a +9,0 del control), a cambio de unos puntos en audio limpio.
- Evaluado en inglés con figuras públicas: en producción se presenta como alerta («probablemente…», con su tasa de
  error), nunca como prueba. Detalle: `evaluacion/resultados/voz_aasist.json`, código en `deteccion_voz/`.

### Entradas de WhatsApp y agente en vivo

- **Nota de voz** → transcripción con Whisper (`faster-whisper`, en el servidor) → afirmación y señales de manipulación
  (urgencia, «reenvía», fuente vaga) → detector de voz → el agente busca qué fuentes la respaldan.
- **Captura de pantalla** → Claude (visión, Bedrock) lee el texto → afirmación → procedencia/IA/filtros de la imagen →
  el agente la investiga. La extensión puede capturar la pestaña actual.
- **Agente en vivo** (`POST /api/agente`, eventos SSE): búsqueda con Exa, lectura, extracción con el modelo y la decisión
  sobre cada página se muestran a medida que ocurren, con un grafo de procedencia interactivo.
- **Conclusiones en lenguaje sencillo**: cada resultado empieza con un semáforo, qué está confirmado y qué hacer; lo
  técnico queda plegado. La web es bilingüe (ES/EN).

## Estructura

```
corpus/       generador y mini-internet sintético (desarrollo + prueba retenida + procedencia C2PA)
motor/        config, cliente LLM agnóstico, extracción, línea base, hechos, buscador, análisis, procedencia, voz
deteccion_voz/ experimento AASIST con códec tipo WhatsApp; modelo AASIST (MIT, NAVER) y pesos
despliegue/   AWS (aws.sh), Caddy y configuración del servidor público
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

Datos sintéticos o públicos: no se analizaron sitios reales de terceros. El mini-internet, sus fotos y sus certificados
son ficticios. El experimento de voz usa el dataset público In-the-Wild (CC-BY-SA 4.0, Müller et al.) y el modelo
AASIST (MIT, NAVER Corp.). El código fue escrito con asistencia de
Claude (Anthropic) y se declara como material generado con IA. Las respuestas de los modelos usados en la
evaluación están en `.cache/llm/` para auditoría.
