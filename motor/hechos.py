"""
Método ECO por hechos atómicos.

1. Un LLM lee todas las páginas de un escenario y lista los hechos atómicos verificables,
   indicando en qué páginas aparece cada uno. Dos redacciones distintas del mismo dato
   cuentan como el mismo hecho, así que la paráfrasis no engaña al conteo.
2. Sin LLM, en orden cronológico: una página es fuente independiente si aporta al menos
   `min_novedad` hechos que ninguna página anterior había publicado. Si no aporta nada nuevo,
   es derivada y se asigna a la página anterior con la que más hechos comparte
   (o a la que enlaza explícitamente).
3. Para cada hecho se cuenta cuántas fuentes independientes lo respaldan: eso separa lo que
   está corroborado de lo que depende de un solo origen.

Atribuciones: el LLM marca como "atribucion" las frases que solo citan quién informó algo
("la empresa lo confirmó en un comunicado"). No cuentan como aporte propio: citar no es reportar.

Variante híbrida (umbral_copia): aunque una página aporte hechos nuevos, se marca como derivada
si su texto es casi idéntico a una página anterior. Esto detecta copias que agregan detalles
inventados para parecer reportería propia, siempre que no reescriban el texto copiado.
"""

from datetime import datetime

from .linea_base import matriz_similitud
from .llm import ClienteLLM

MAX_CARACTERES_PAGINA = 3000

SISTEMA = """Eres un analista de verificación de información. Recibes varias páginas web que hablan de la misma afirmación.
Tu tarea es listar los hechos atómicos verificables que aparecen en las páginas e indicar en qué páginas aparece cada uno.

Reglas:
- Un hecho atómico es una sola afirmación concreta y comprobable: un dato, una cifra, una causa, un lugar, una fecha, una medida tomada, o un testimonio atribuido a alguien.
- Si dos frases dicen lo mismo con distintas palabras, son el MISMO hecho: márcalo en todas las páginas donde aparece.
- Si una frase aporta un dato distinto (otra cifra, otro testimonio, otra persona, otro barrio), es un hecho DISTINTO.
- Divide las frases que contengan varios datos en hechos separados.
- No incluyas frases genéricas o no verificables (por ejemplo: "la noticia generó preocupación", "la situación sigue en desarrollo", "se espera más información", invitaciones a compartir).
- Clasifica cada hecho con "tipo":
  - "dato": información sobre el suceso (qué pasó, cifras, lugares, fechas, medidas, causas, testimonios con su contenido).
  - "atribucion": frases sobre la noticia y no sobre el suceso: quién informó, confirmó, publicó o comunicó algo; que remiten a otra fuente, medio o comunicado; o que comentan su difusión (que es tendencia, que circula o se comparte en redes o en chats).
- No partas un mismo dato en sub-detalles: "el acueducto suspendió el servicio" y "la suspensión fue ordenada por el acueducto" son el mismo hecho.
- Usa solo lo que dicen las páginas. No agregues conocimiento propio."""

FORMATO = """Devuelve JSON con esta forma exacta:
{"hechos": [{"id": "H1", "texto": "enunciado breve del hecho", "tipo": "dato", "paginas": ["P1", "P3"]}]}"""


def construir_prompt(afirmacion, documentos):
    """Devuelve (prompt, etiquetas) donde etiquetas mapea P1..Pn -> id del documento.
    Las páginas se presentan ordenadas por id, no por fecha, para no sesgar al modelo."""
    ordenados = sorted(documentos, key=lambda d: d.id)
    etiquetas = {f"P{i}": d.id for i, d in enumerate(ordenados, start=1)}
    bloques = []
    for etiqueta, d in zip(etiquetas, ordenados):
        texto = d.texto[:MAX_CARACTERES_PAGINA]
        bloques.append(f"[{etiqueta}] {d.sitio}\n{texto}")
    prompt = (f"Afirmación analizada: {afirmacion}\n\n" + "\n\n".join(bloques) + f"\n\n{FORMATO}")
    return prompt, etiquetas


def extraer_hechos(afirmacion, documentos, cliente=None):
    cliente = cliente or ClienteLLM()
    prompt, etiquetas = construir_prompt(afirmacion, documentos)
    datos, respuesta = cliente.completar_json(prompt, sistema=SISTEMA)
    hechos = []
    for h in datos.get("hechos", []):
        paginas = [etiquetas[p] for p in h.get("paginas", []) if p in etiquetas]
        if paginas:
            tipo = "atribucion" if str(h.get("tipo", "dato")).lower().startswith("atrib") else "dato"
            hechos.append({"id": str(h.get("id", f"H{len(hechos) + 1}")), "texto": h.get("texto", ""),
                           "tipo": tipo, "paginas": paginas})
    return hechos, respuesta


DISTANCIA_MISMA_FOTO = 8  # bits de 64 en la huella visual


def _fecha(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")) if iso else None
    except (ValueError, AttributeError):
        return None


def distancia_huella(h1, h2):
    from .procedencia import distancia
    return distancia(h1, h2)


def _firmas_por_pagina(documentos, procedencia):
    """Para cada página, las firmas confiables de sus fotos: directas (C2PA) o reconocidas por la huella
    visual de una foto firmada en otra página (la misma foto sin metadatos, p. ej. tras recomprimirla)."""
    conocidas = [(im["huella"], im["firmante"], im.get("fecha_firmada"))
                 for infos in procedencia.values() for im in infos
                 if im.get("estado") == "confiable" and im.get("firmante") and im.get("huella")]
    firmas = {}
    for d in documentos:
        lista = []
        for im in procedencia.get(d.id, []):
            if im.get("estado") == "confiable" and im.get("firmante"):
                lista.append({"firmante": im["firmante"], "fecha": im.get("fecha_firmada"), "via": "firma C2PA"})
            elif im.get("estado") in ("ausente", "valida_no_confiable") and im.get("huella"):
                for h, firmante, fecha in conocidas:
                    if distancia_huella(im["huella"], h) <= DISTANCIA_MISMA_FOTO:
                        lista.append({"firmante": firmante, "fecha": fecha,
                                      "via": "misma foto sin metadatos, reconocida por su huella visual"})
                        break
        firmas[d.id] = lista
    return firmas


def analizar(documentos, afirmacion, cliente=None, min_novedad=1, hechos=None, umbral_copia=None, procedencia=None):
    """
    documentos: lista de Documento. afirmacion: texto de la afirmación.
    hechos: opcional, para reutilizar una extracción previa.
    umbral_copia: si se indica (0 a 1), activa la variante híbrida.
    Devuelve el mismo formato que linea_base.analizar, más detalle por página y por hecho.
    """
    n = len(documentos)
    if n == 0:
        return {"metodo": "hechos", "fuentes_aparentes": 0, "fuentes_efectivas": 0, "grupos": [],
                "paginas": [], "hechos": []}

    respuesta = None
    if hechos is None:
        hechos, respuesta = extraer_hechos(afirmacion, documentos, cliente)

    # Las atribuciones ("X confirmó mediante un comunicado") solo citan la fuente: no son aporte propio.
    atribuciones = [h for h in hechos if h.get("tipo") == "atribucion"]
    hechos = [h for h in hechos if h.get("tipo") != "atribucion"]
    por_id = {d.id: d for d in documentos}
    hechos_de = {d.id: {h["id"] for h in hechos if d.id in h["paginas"]} for d in documentos}
    indice = {d.id: i for i, d in enumerate(documentos)}
    por_url = {d.url: d.id for d in documentos}
    sim = matriz_similitud(documentos) if n > 1 else [[1.0]]

    # Procedencia (C2PA): la fecha firmada de una foto es un límite inferior para la página que la usa.
    procedencia = procedencia or {}
    firmas = _firmas_por_pagina(documentos, procedencia)
    fecha_ef, nota_fecha = {}, {}
    for d in documentos:
        f = d.fecha
        for fm in firmas[d.id]:
            ff = _fecha(fm["fecha"])
            try:
                posterior = ff is not None and (f is None or ff > f)
            except TypeError:  # fechas con y sin zona horaria
                posterior = False
            if posterior:
                nota_fecha[d.id] = (f"declara {d.fecha.isoformat() if d.fecha else 'sin fecha'}, pero usa una foto que "
                                    f"{fm['firmante']} firmó el {fm['fecha']}: no pudo publicarse antes")
                f = ff
        fecha_ef[d.id] = f

    def foto_ajena(d, anteriores):
        """Foto firmada por otro medio del conjunto que publicó antes, sin foto propia firmada."""
        if any(fm["firmante"] == d.sitio for fm in firmas[d.id]):
            return None
        for fm in firmas[d.id]:
            for a in anteriores:
                if a.sitio == fm["firmante"]:
                    return a.id, fm
        return None

    def firma_propia(d):  # a igual fecha, primero quien firmó su propia foto
        return 0 if any(fm["firmante"] == d.sitio and fm["via"] == "firma C2PA" for fm in firmas[d.id]) else 1

    orden = sorted(documentos, key=lambda d: (fecha_ef[d.id] is None,
                                              fecha_ef[d.id].timestamp() if fecha_ef[d.id] else 0,
                                              firma_propia(d), d.id))
    vistos = set()
    detalle = {}
    for pos, d in enumerate(orden):
        propios = hechos_de[d.id]
        nuevos = propios - vistos
        anteriores = orden[:pos]
        enlazadas = [por_url[u] for u in d.enlaces if u in por_url and por_url[u] in {a.id for a in anteriores}]
        independiente = pos == 0 or len(nuevos) >= min_novedad
        motivo = "primera publicación" if pos == 0 else ("aporta hechos nuevos" if independiente else "no aporta hechos nuevos")
        madre = None
        if independiente and pos > 0 and umbral_copia is not None:
            mas_parecida = max(anteriores, key=lambda a: sim[indice[d.id]][indice[a.id]])
            if sim[indice[d.id]][indice[mas_parecida.id]] >= umbral_copia:
                independiente = False
                madre = mas_parecida.id
                motivo = "texto casi idéntico a una página anterior, con datos agregados"
        if independiente and pos > 0 and firmas[d.id]:
            ajena = foto_ajena(d, anteriores)
            if ajena:
                independiente = False
                madre = ajena[0]
                motivo = (f"usa la foto firmada por {ajena[1]['firmante']} ({ajena[1]['via']}), "
                          f"que publicó antes, y no tiene foto propia firmada")
        if not independiente and madre is None:
            if enlazadas:
                madre = enlazadas[0]
            else:
                def afinidad(a):
                    comunes = len(propios & hechos_de[a.id])
                    return (comunes / max(len(propios), 1), sim[indice[d.id]][indice[a.id]])
                madre = max(anteriores, key=afinidad).id
        detalle[d.id] = {
            "id": d.id, "sitio": d.sitio, "dominio": d.dominio,
            "fecha": d.fecha.isoformat() if d.fecha else None,
            "independiente": independiente, "deriva_de": madre, "motivo": motivo,
            "hechos": sorted(propios), "hechos_nuevos": sorted(nuevos),
            "fecha_efectiva": fecha_ef[d.id].isoformat() if fecha_ef[d.id] else None,
            "nota_fecha": nota_fecha.get(d.id),
            "imagenes": [{k: im.get(k) for k in ("url", "estado", "firmante", "fecha_firmada", "generada_por_ia",
                                                  "fuente_digital", "codigos", "huella")}
                         for im in procedencia.get(d.id, [])],
            "firmas_reconocidas": firmas[d.id],
        }
        vistos |= propios

    def raiz(pid):
        visitados = set()
        while detalle[pid]["deriva_de"] and pid not in visitados:
            visitados.add(pid)
            pid = detalle[pid]["deriva_de"]
        return pid

    grupos_map = {}
    for d in orden:
        grupos_map.setdefault(raiz(d.id), []).append(d.id)
    grupos = []
    for origen, miembros in grupos_map.items():
        grupos.append({
            "origen": origen,
            "origen_sitio": por_id[origen].sitio,
            "origen_fecha": detalle[origen]["fecha"],
            "miembros": miembros,
            "dominios": sorted({por_id[m].dominio for m in miembros}),
            "derivaciones": [{"pagina": m, "deriva_de": detalle[m]["deriva_de"]} for m in miembros if m != origen],
            "aporte": detalle[origen]["hechos_nuevos"],
        })
    grupos.sort(key=lambda g: g["origen_fecha"] or "")

    grupo_de = {m: g["origen"] for g in grupos for m in g["miembros"]}
    resumen_hechos = []
    for h in hechos:
        fuentes = sorted({grupo_de[p] for p in h["paginas"]})
        resumen_hechos.append({**h, "fuentes_independientes": len(fuentes), "grupos": fuentes})
    resumen_hechos.sort(key=lambda h: -h["fuentes_independientes"])

    return {
        "metodo": "hibrido" if umbral_copia is not None else "hechos",
        "min_novedad": min_novedad,
        "umbral_copia": umbral_copia,
        "fuentes_aparentes": n,
        "fuentes_efectivas": len(grupos),
        "grupos": grupos,
        "paginas": [detalle[d.id] for d in orden],
        "hechos": resumen_hechos,
        "atribuciones": [h["texto"] for h in atribuciones],
        "corroborados": [h["texto"] for h in resumen_hechos if h["fuentes_independientes"] >= 2],
        "de_un_solo_origen": [h["texto"] for h in resumen_hechos if h["fuentes_independientes"] < 2],
        "procedencia": _resumen_procedencia(procedencia, nota_fecha, detalle) if procedencia else None,
        "modelo": respuesta.modelo if respuesta else None,
        "desde_cache": respuesta.desde_cache if respuesta else None,
        "segundos_llm": respuesta.segundos if respuesta else None,
    }


def _resumen_procedencia(procedencia, nota_fecha, detalle):
    imagenes = [im for infos in procedencia.values() for im in infos]
    return {
        "imagenes": len(imagenes),
        "firmadas_confiables": sum(im.get("estado") == "confiable" for im in imagenes),
        "firma_rota": [pid for pid, infos in procedencia.items() if any(im.get("estado") == "rota" for im in infos)],
        "generadas_por_ia": [pid for pid, infos in procedencia.items() if any(im.get("generada_por_ia") for im in infos)],
        "fechas_imposibles": [{"pagina": pid, "nota": nota} for pid, nota in nota_fecha.items()],
        "por_foto_ajena": [pid for pid, det in detalle.items() if det["motivo"].startswith("usa la foto firmada")],
        "aviso": ("C2PA prueba quién firmó y cuándo, no que el contenido sea cierto. Una imagen sin firma no es "
                  "sospechosa por sí sola: casi todo el contenido real no la trae."),
    }
