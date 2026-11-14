"""
Servidor MCP de ECO.

Da a un agente (Claude Desktop, Claude Code u otro cliente MCP) herramientas para revisar si
las fuentes que encontró son realmente independientes antes de decir que algo está confirmado.

Arranque (stdio), desde la carpeta eco:
  python -m mcp_eco.servidor

Herramientas:
  evaluar_corroboracion(afirmacion, urls)   analiza un conjunto de URLs (reales o del mini-internet)
  buscar_en_mini_internet(consulta)          encuentra mundos del laboratorio sintético
  analizar_mundo(mundo_id)                   analiza un mundo completo del laboratorio
  verificar_procedencia(url_imagen)          firma C2PA de una imagen: quién la firmó, cuándo, si se declara IA
"""

import sys
from pathlib import Path

# Permite arrancar el servidor desde cualquier carpeta (los clientes MCP no siempre fijan el directorio).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:  # SDK de MCP 2.x
    from mcp.server.mcpserver import MCPServer as _Servidor
except ImportError:  # SDK de MCP 1.x
    from mcp.server.fastmcp import FastMCP as _Servidor

from motor import buscador  # noqa: E402
from motor import procedencia  # noqa: E402
from motor.analisis import analizar_urls  # noqa: E402

INSTRUCCIONES = (
    "ECO verifica la independencia de fuentes. Antes de afirmar que algo está confirmado por varias fuentes, "
    "llama a evaluar_corroboracion con la afirmación y las URLs que encontraste. Muchas páginas que repiten lo mismo "
    "pueden venir de un solo origen; en ese caso no cuentan como confirmación. Informa al usuario cuántas fuentes "
    "independientes hay, cuál es el origen probable y qué datos dependen de una sola fuente. ECO no determina si algo "
    "es verdadero: mide cuánta evidencia independiente lo respalda."
)

mcp = _Servidor("eco", instructions=INSTRUCCIONES)


def _compacto(res):
    """Resultado reducido para no saturar el contexto del agente."""
    return {
        "resumen": res["resumen"],
        "fuentes_aparentes": res["fuentes_aparentes"],
        "fuentes_independientes": res["fuentes_efectivas"],
        "metodo": res["metodo"],
        "grupos": [{"origen": g["origen"], "origen_sitio": g["origen_sitio"], "origen_fecha": g["origen_fecha"],
                    "paginas": g["miembros"]} for g in res["grupos"]],
        "datos_corroborados": res.get("corroborados", []),
        "datos_de_una_sola_fuente": res.get("de_un_solo_origen", []),
        "frases_sobre_la_noticia_excluidas": res.get("atribuciones", []),
        "paginas": [{"id": d["id"], "sitio": d["sitio"], "url": d["url"], "fecha": d["fecha"]} for d in res["documentos"]],
        "procedencia": res.get("procedencia"),
        "fechas_corregidas_por_firma": [{"pagina": p["id"], "nota": p["nota_fecha"]}
                                        for p in res.get("paginas", []) if p.get("nota_fecha")],
        "urls_con_error": res.get("urls_con_error", []),
        "aviso": res.get("aviso"),
    }


@mcp.tool()
def evaluar_corroboracion(afirmacion: str, urls: list[str]) -> dict:
    """Mide cuántas fuentes independientes respaldan una afirmación.

    Recibe la afirmación y las URLs de las páginas que la mencionan (2 a 40). Devuelve cuántas
    fuentes son realmente independientes, el origen probable de cada grupo de copias y qué datos
    están corroborados por fuentes independientes frente a los que dependen de una sola.
    """
    if not urls:
        return {"error": "Se necesita al menos una URL."}
    return _compacto(analizar_urls(afirmacion, urls[:40]))


@mcp.tool()
def buscar_en_mini_internet(consulta: str, max_resultados: int = 5) -> list[dict]:
    """Busca en el mini-internet sintético de ECO (laboratorio de pruebas, contenido ficticio).

    Devuelve mundos: cada uno es un pequeño internet con varias páginas sobre una afirmación.
    Use analizar_mundo o evaluar_corroboracion con las URLs devueltas.
    """
    return [{"mundo_id": m["id"], "afirmacion": m["afirmacion"], "parecido": m["parecido"],
             "paginas": [{"medio": p["medio"], "titulo": p["titulo"], "url": p["url"]} for p in m["paginas"]]}
            for m in buscador.buscar(consulta, max_resultados)]


@mcp.tool()
def analizar_mundo(mundo_id: str) -> dict:
    """Analiza todas las páginas de un mundo del mini-internet sintético (por ejemplo 'e01-s1')."""
    mundo = next((m for m in buscador._indice() if m["id"] == mundo_id), None)
    if mundo is None:
        return {"error": f"No existe el mundo {mundo_id}."}
    res = _compacto(analizar_urls(mundo["afirmacion"], [p["url"] for p in mundo["paginas"]]))
    res["mundo_id"] = mundo_id
    res["afirmacion"] = mundo["afirmacion"]
    return res


def _app_http():
    """Versión HTTP (Streamable HTTP) del mismo servidor; api.servidor agrega su ruta /mcp.
    Sin estado y con respuestas JSON: sirve detrás de Cloudflare y para varios agentes a la vez."""
    try:
        from mcp.server.transport_security import TransportSecuritySettings
        seguridad = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    except ImportError:
        seguridad = None
    return mcp.streamable_http_app(streamable_http_path="/mcp", stateless_http=True, json_response=True,
                                   transport_security=seguridad)


app_http = _app_http()


@mcp.tool()
def verificar_procedencia(url_imagen: str) -> dict:
    """Verifica la procedencia criptográfica (C2PA) de una imagen.

    Devuelve si trae credenciales de contenido, si la firma es válida y de un emisor confiable, quién la firmó,
    la fecha de publicación firmada, si se declara generada por IA y si fue alterada después de firmarse.
    Una imagen sin firma NO es sospechosa por sí sola: casi todo el contenido real no la trae.
    """
    try:
        datos = procedencia._bytes_imagen(url_imagen)
    except Exception as e:
        return {"error": f"No se pudo descargar la imagen: {type(e).__name__}: {e}"}
    sufijo = url_imagen.split("?")[0].rsplit(".", 1)[-1].lower()
    info = procedencia.verificar(datos, procedencia.TIPOS_MIME.get("." + sufijo, "image/jpeg"))
    info["url"] = url_imagen
    info["interpretacion"] = {
        "confiable": "Firma íntegra de un emisor de la lista de confianza.",
        "valida_no_confiable": "La firma es íntegra, pero el emisor no está en la lista de confianza.",
        "rota": "La imagen cambió después de firmarse: no confíe en lo que dice el manifiesto.",
        "ausente": "No trae credenciales de contenido (lo normal en internet hoy).",
    }.get(info["estado"], "No se pudo verificar.")
    return info


def main():
    mcp.run("stdio")


if __name__ == "__main__":
    main()
