# Guía de la demo y del pitch

## Dónde está

- **En línea, desde cualquier red:** <https://eco.kibosecondbrain.com> (AWS + Cloudflare).
- **Instalar extensión y MCP:** pestaña *Instalar* → <https://eco.kibosecondbrain.com/#instalar>.
- **MCP remoto:** `claude mcp add --transport http eco https://eco.kibosecondbrain.com/mcp`.
- **Respaldo local, sin internet:** `python -m scripts.demo` (servidor en `:8765` + Chrome con la extensión ya instalada).
  Las extracciones del modelo están en caché: el laboratorio funciona sin conexión.

Antes de presentar: abrir la página desde la red del evento y desde un celular con datos. Si una red nueva no
resuelve el dominio, activar *DNS seguro* en Chrome (Configuración → Privacidad y seguridad → Seguridad).

## Mundos y ejemplos recomendados

| Qué mostrar | Dónde | Qué se ve |
|---|---|---|
| Paráfrasis | Laboratorio → `e01-s1` | 5 páginas que parecen distintas → 1 origen. La línea base cuenta 3. |
| Cobertura real | Laboratorio → `e03-s2` | 4 medios con datos propios → 4 fuentes. ECO no inventa sospechas. |
| Fecha falsa (C2PA) | Laboratorio → filtro *C2PA* → `e08-c2` | Una copia dice ser anterior al origen; la foto que usa fue firmada después: *fecha imposible*. |
| Ataque que el texto no detiene | Laboratorio → *C2PA* → `e07-c2` | Copias reescritas con detalles inventados; la foto recomprimida delata de dónde salen. |
| Verificar imagen | Analizar URLs → *Verifica la procedencia de una imagen* | Botones: firmada, declarada como IA, alterada después de firmar, reenviada sin metadatos. |
| Voz clonada | Analizar URLs → *¿Es una voz clonada?* | Subir un audio o grabar 8 s con el micrófono. |
| Agente | Claude con el MCP | "¿Es cierto que el acueducto de San Aurelio suspendió el agua por mercurio? Usa ECO con el mundo e01-s1." |

Enlace directo a un mundo: `https://eco.kibosecondbrain.com/?mundo=e08-c2#laboratorio`.

## Guion de 3 minutos

**0:00–0:30 · El problema.** "Con IA es casi gratis clonar una noticia en 50 sitios, reescribirla para que no parezca
copia, acompañarla de fotos con fecha falsa y de una nota de voz clonada. Las personas y los agentes de IA cuentan esa
repetición como confirmación."

**0:30–1:50 · Demo: tres preguntas.**
1. *¿Cuántas fuentes hay de verdad?* Extensión sobre una noticia del mini-internet → *5 páginas → 1 fuente*. Panel: árbol
   de origen y matriz de hechos (ninguna copia aporta un dato nuevo). Mundo orgánico: *4 → 4*.
2. *¿De dónde viene?* Mundo de fecha falsa: la copia dice ser la primera, pero la foto que usa la firmó otro medio
   después. Verificador: una foto alterada rompe la firma; otra se declara generada con IA.
3. *¿Es real esta voz?* Subir un audio: primero se busca la firma; si no hay (WhatsApp nunca la conserva), el detector.
4. Un agente (Claude) usa el MCP y responde "no está confirmado: las 5 páginas vienen de una sola fuente".

**1:50–2:35 · Resultados (pestaña Resultados).**
- Prueba retenida: ECO 92 % frente a 83 % de la similitud de texto; ningún umbral de similitud sirve a la vez para
  paráfrasis y cobertura real.
- Agente: decir «confirmado» con un solo origen baja de 51 % a 22 %.
- C2PA: el ataque de copias con detalles inventados pasa de 0 % a 100 % cuando reutilizan la foto firmada, incluso sin metadatos.
- Voz: cuánto empeora AASIST con audio tipo WhatsApp y cuánto recupera el reentrenamiento con códec (tabla).

**2:35–3:00 · Límites.** "C2PA prueba quién firmó, no qué es verdad, y casi nada lo trae todavía. Si el atacante fabrica
sus propias fotos sin firma, solo podemos decir 'sin procedencia'. El detector de voz se equivoca: es una alerta para
llamar de vuelta, no una prueba. Y ECO mide independencia, no verdad."

## Preguntas probables del jurado

- **¿Cómo consiguen las URLs en la web real?** El agente ya las tiene de su búsqueda; el MCP recibe la afirmación y las
  URLs. En el panel, *Analizar URLs* hace lo mismo. La extensión, por ahora, encuentra páginas relacionadas solo en el mini-internet.
- **¿Por qué C2PA si casi nadie lo usa?** Porque es la única señal que el atacante no controla: no puede firmar como otro
  medio. Cámaras, editores y medios lo están adoptando; ECO lo aprovecha donde existe y degrada con honestidad donde no.
- **¿La fecha firmada no la puede inventar el firmante?** Sí: aquí la declara el firmante. En producción se usa un sello
  de tiempo RFC 3161 de un tercero. Igual, una copia no puede usar la firma del origen con una fecha anterior a ella.
- **¿El detector de voz sirve en español?** Se evaluó en inglés (In-the-Wild). No lo afirmamos para español; por eso lo
  presentamos como alerta y medimos la degradación por canal, que es lo que más daña en la práctica.
- **¿No es caro?** Una llamada al LLM por conjunto de páginas. La regla, C2PA y la huella visual no usan LLM; el detector
  de voz corre en CPU. El servidor público limita peticiones por IP y tiene un tope diario de llamadas al modelo.
- **¿Doble uso?** Un atacante podría usar ECO o el detector como oráculo. Mitigación: límites de uso, no publicar
  umbrales de producción y priorizar señales que el atacante no controla (firmas de terceros).
