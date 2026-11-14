# Guía de la demo y del pitch

## Antes de salir de casa

1. Entorno: `python -m venv .venv`, activar, `pip install -r requirements.txt`, `.env` con las claves.
2. `python -m pruebas.prueba_humo` → todo en OK.
3. Modelo: por defecto `claudecode/sonnet` (la CLI de Claude Code con sesión iniciada; no necesita clave de API).
   Las 54 extracciones ya están en caché, así que la demo del mini-internet funciona sin conexión.
   Para usar OpenRouter hace falta una clave **de inferencia** (`sk-or-v1-…`, de openrouter.ai/settings/keys);
   una clave de *gestión* responde `401 User not found`.
4. MCP: `python -m scripts.config_mcp --instalar` y reiniciar Claude Desktop. Verificar: `python -m scripts.probar_mcp`.
5. Ensayar con `python -m scripts.demo` (abre servidor + navegador con la extensión).

## Arranque el día de la demo (un comando)

```bash
python -m scripts.demo
```

Arranca el servidor en `http://localhost:8765` y abre un Chrome for Testing con la extensión ya instalada,
con el panel de ECO y una página del mini-internet. Si el puerto está ocupado: `python -m scripts.demo --puerto 8770`
y en el popup de la extensión → «Servidor de ECO» → `http://localhost:8770`.

## Mundos recomendados para mostrar

| Mundo | Qué muestra |
|---|---|
| `e01-s1` | Paráfrasis: 5 páginas que parecen distintas, 1 origen. La línea base cuenta 3 fuentes. |
| `e03-s2` | Cobertura orgánica: 4 medios con datos propios, 4 fuentes. ECO no inventa sospechas. |
| `e01-s3` | Comunicado oficial: muchas páginas, una sola fuente (el comunicado). |
| `e01-x1` | Fabricado paráfrasis, el límite: copias reescritas que inventan detalles. ECO se equivoca y lo decimos. |

Enlace directo: `http://localhost:8765/?mundo=e01-s1#laboratorio`.

## Guion de 3 minutos

**0:00–0:30 · El problema.** "Con IA es casi gratis clonar una mentira en 50 sitios y reescribirla para que no parezca copia.
Las personas y los agentes con búsqueda web cuentan esa repetición como confirmación."

**0:30–1:40 · Demo.**
1. Página del mini-internet → clic derecho → *ECO: ¿cuántas fuentes reales…?* Panel: *5 páginas → 1 fuente*, "esta página" dentro de la cadena de copias.
2. Clic en *Ver árbol de origen…* → panel web: árbol en el tiempo, **matriz de hechos** (ninguna copia aporta un dato nuevo) y la comparación
   *aparentes 5 · línea base 3 · ECO 1 · correcta 1* (botón Revelar).
3. Mundo orgánico `e03-s2`: *4 → 4*. ECO no ve fantasmas.
4. Claude con el MCP: "¿Es cierto que el acueducto de San Aurelio suspendió el agua por mercurio? Usa ECO con el mundo e01-s1."

**1:40–2:30 · Resultados.** Pestaña *Resultados*: la similitud de texto falla en paráfrasis; ningún umbral sirve a la vez
para orgánico y paráfrasis (gráfico del barrido). ECO por hechos lo resuelve. Gráfico del agente: sobreconfirmación sin ECO vs. con ECO.

**2:30–3:00 · Límites.** "El ataque caro sigue abierto: reescribir e inventar detalles en cada copia. Y la calidad depende del modelo
extractor: un modelo local de 7B confunde 'tres días' con '72 horas'. ECO mide independencia, no verdad."

## Preguntas probables del jurado

- **¿Cómo consiguen las URLs en la web real?** El agente ya las tiene de su búsqueda; el MCP recibe la afirmación y las URLs.
  En el panel, la pestaña *Analizar URLs* hace lo mismo. La extensión, por ahora, encuentra las páginas relacionadas solo en el mini-internet.
- **¿No es caro?** Una llamada al LLM por conjunto de páginas, no por página. La regla de independencia no usa LLM. Funciona con un modelo local (Ollama), sin enviar datos afuera.
- **¿Y si el LLM se equivoca extrayendo hechos?** Por eso se publica la línea base, se comparan modelos y se reportan las fallas.
  Las respuestas quedan en caché y se pueden auditar.
- **¿Doble uso?** Un atacante podría usar ECO para probar sus copias hasta que pasen. Mitigación: no publicar umbrales
  de producción y combinar con señales de procedencia (C2PA, firmas) que el atacante no controla.
