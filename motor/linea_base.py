"""
Línea base de ECO: agrupa páginas que son copia unas de otras usando solo
similitud de texto (TF-IDF de n-gramas de caracteres) y enlaces explícitos.

Cada grupo cuenta como una fuente independiente. El origen de cada grupo es la
página más antigua. Esta es la referencia contra la que se compara el método
por hechos atómicos de los pasos siguientes.
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .config import config


class _UnionFind:
    def __init__(self, n):
        self.padre = list(range(n))

    def buscar(self, i):
        while self.padre[i] != i:
            self.padre[i] = self.padre[self.padre[i]]
            i = self.padre[i]
        return i

    def unir(self, a, b):
        self.padre[self.buscar(a)] = self.buscar(b)


def _clave_fecha(doc, i):
    # Documentos sin fecha van al final; a igualdad, por orden de llegada.
    return (doc.fecha is None, doc.fecha.timestamp() if doc.fecha else 0, i)


def matriz_similitud(documentos):
    textos = [d.texto or d.titulo for d in documentos]
    vectorizador = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, lowercase=True)
    return cosine_similarity(vectorizador.fit_transform(textos))


def analizar(documentos, umbral=None):
    """
    documentos: lista de motor.extraccion.Documento
    Devuelve un dict con fuentes aparentes, fuentes efectivas, grupos y aristas.
    """
    umbral = config.umbral_similitud if umbral is None else umbral
    n = len(documentos)
    if n == 0:
        return {"metodo": "linea_base", "umbral": umbral, "fuentes_aparentes": 0,
                "fuentes_efectivas": 0, "grupos": [], "aristas": []}

    sim = matriz_similitud(documentos) if n > 1 else [[1.0]]
    uf = _UnionFind(n)
    aristas = []
    por_url = {d.url: i for i, d in enumerate(documentos)}

    for i in range(n):
        for j in range(i + 1, n):
            if sim[i][j] >= umbral:
                uf.unir(i, j)
                aristas.append({"a": documentos[i].id, "b": documentos[j].id,
                                "motivo": "similitud", "valor": round(float(sim[i][j]), 3)})
    for i, d in enumerate(documentos):
        for enlace in d.enlaces:
            j = por_url.get(enlace)
            if j is not None and j != i:
                uf.unir(i, j)
                aristas.append({"a": d.id, "b": documentos[j].id, "motivo": "enlace",
                                "valor": round(float(sim[i][j]), 3)})

    miembros = {}
    for i in range(n):
        miembros.setdefault(uf.buscar(i), []).append(i)

    grupos = []
    for indices in miembros.values():
        ordenados = sorted(indices, key=lambda k: _clave_fecha(documentos[k], k))
        origen = ordenados[0]
        derivaciones = []
        for pos, k in enumerate(ordenados[1:], start=1):
            # Madre estimada: la página anterior del grupo más parecida a esta.
            anteriores = ordenados[:pos]
            madre = max(anteriores, key=lambda m: sim[k][m])
            derivaciones.append({"pagina": documentos[k].id, "deriva_de": documentos[madre].id,
                                 "similitud": round(float(sim[k][madre]), 3)})
        grupos.append({
            "origen": documentos[origen].id,
            "origen_sitio": documentos[origen].sitio,
            "origen_fecha": documentos[origen].fecha.isoformat() if documentos[origen].fecha else None,
            "miembros": [documentos[k].id for k in ordenados],
            "dominios": sorted({documentos[k].dominio for k in ordenados}),
            "derivaciones": derivaciones,
        })
    grupos.sort(key=lambda g: (-len(g["miembros"]), g["origen_fecha"] or ""))

    return {
        "metodo": "linea_base",
        "umbral": umbral,
        "fuentes_aparentes": n,
        "fuentes_efectivas": len(grupos),
        "grupos": grupos,
        "aristas": aristas,
    }
