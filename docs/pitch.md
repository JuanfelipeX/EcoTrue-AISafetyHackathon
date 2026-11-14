# Pitch de 3 minutos — ECO

> Ritmo: ~150 palabras por minuto. Entre corchetes, lo que se muestra en pantalla.
> Antes de subir: abrir https://eco.kibosecondbrain.com (pestaña Verificar) y tener a mano la nota de voz de prueba.

---

**[0:00 – 0:20] El gancho**

Les llega este audio por WhatsApp. *[reproducir 5 segundos de la nota de voz]* "Urgente, reenvíen a todos: mañana cortan
el agua en todo Bogotá por mercurio, me lo dijo un primo que trabaja en el acueducto".
Lo buscan en Google… y aparece en ocho páginas. ¿Es cierto?

**[0:20 – 0:45] El problema**

Con IA es casi gratis clonar una noticia en decenas de sitios y reescribirla para que no parezca copia. Es gratis
fabricar una foto con fecha falsa. Y es gratis clonar una voz.
Las personas —y también los agentes de IA que buscan en la web— cuentan esa repetición como confirmación.
Ocho páginas parecen ocho fuentes. Muchas veces son **una sola**.

**[0:45 – 1:05] Qué es ECO**

ECO es una defensa epistémica que responde tres preguntas, en una frase que cualquiera entiende:
**¿cuántas fuentes hay de verdad?, ¿de dónde viene esta imagen y la hizo una IA?, y ¿es real esta voz?**
No dice qué es verdad. Muestra la evidencia para que decidas.

**[1:05 – 2:00] Demo en vivo**

*[Verificar → Nota de voz → subir el audio]*
ECO transcribe el audio, saca lo que afirma y marca las señales de manipulación: urgencia, "reenvíen", fuente vaga.
Y nos dice: **probablemente voz sintética**. *[señalar la tarjeta roja]*

*[clic en "Verificar qué fuentes lo respaldan"]*
Ahora el agente trabaja en vivo: busca, lee cada nota, un modelo extrae los datos y una regla auditable decide medio
por medio quién aporta información propia y quién solo repite. *[señalar la bitácora y el grafo]*
Conclusión: *[leer la tarjeta]*.

*[Extensión en una noticia real → clic derecho sobre una foto]*
Lo mismo funciona como extensión del navegador, sobre cualquier noticia o imagen.
Y como servidor MCP: un agente como Claude lo consulta **antes** de decir "varias fuentes lo confirman".

**[2:00 – 2:35] La evidencia**

*[pestaña Resultados]*
Lo medimos con respuesta conocida:
- En mundos que nunca usamos para ajustar, ECO acierta el **92 %** frente al **83 %** de comparar textos, y nunca junta
  medios independientes por error.
- Con el informe de ECO, un agente pasó de decir "confirmado" con un solo origen el **51 %** de las veces al **22 %**.
- Con firmas C2PA, las copias reescritas que inventan detalles —el ataque que el texto no detecta— pasan de **0 % a 100 %**
  cuando reutilizan la foto firmada, y la fecha firmada delata a la copia que finge ser el origen.
- Y un hallazgo: los detectores de voz de laboratorio **fallan como una moneda** con voces reales: 48 % de error.
  Reentrenado con audio comprimido como el de WhatsApp, baja a **29 %** y casi no empeora al comprimir.

**[2:35 – 3:00] Honestidad y cierre**

Somos honestos con los límites: C2PA prueba quién firmó, no qué es verdad; el detector de voz se equivoca 29 de cada 100,
por eso es una alerta para llamar de vuelta, nunca una prueba para acusar a alguien.

Ya está desplegado, es bilingüe y cualquiera puede usarlo hoy.
**ECO no te dice qué creer. Te dice cuántas fuentes reales hay detrás de lo que te llega.**

---

## Si sobra tiempo o en preguntas

- **¿Por qué no un detector de imágenes por píxeles?** Fallan con generadores nuevos y acusarían a inocentes. Usamos
  señales que el atacante no controla (firmas de terceros) y mostramos los filtros forenses solo como indicio.
- **¿Cuánto cuesta?** Una llamada al modelo por conjunto de páginas; la regla, C2PA y la huella visual no usan LLM; la voz
  corre en CPU. El servidor limita peticiones por persona y tiene un tope diario.
- **¿Doble uso?** Alguien podría usar ECO para pulir sus copias. Mitigamos con límites de uso, sin publicar umbrales de
  producción, y priorizando firmas que el atacante no puede falsificar.
- **¿Y las agencias como AP?** Si su nota se publica más tarde que una copia, la regla cronológica puede verla como
  repetición: ECO mide quién aporta datos en estas notas, no quién es la agencia de origen. Lo decimos como límite.
