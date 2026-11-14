"""
Extracción de documentos a partir de HTML: título, sitio, dominio, autor, fecha, párrafos y enlaces.

Funciona con las páginas del corpus y, de forma razonable, con páginas reales de noticias
(usa metadatos Open Graph y etiquetas estándar, con alternativas cuando faltan).
"""

import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

CLASES_EXCLUIDAS = {"aviso", "meta", "fuente"}


@dataclass
class Documento:
    id: str
    url: str
    titulo: str = ""
    sitio: str = ""
    dominio: str = ""
    autor: str = ""
    fecha: datetime | None = None
    parrafos: list = field(default_factory=list)
    enlaces: list = field(default_factory=list)
    imagenes: list = field(default_factory=list)

    @property
    def texto(self):
        return "\n".join(self.parrafos)

    def resumen(self):
        return {
            "id": self.id, "url": self.url, "titulo": self.titulo, "sitio": self.sitio,
            "dominio": self.dominio, "autor": self.autor,
            "fecha": self.fecha.isoformat() if self.fecha else None,
            "n_parrafos": len(self.parrafos), "enlaces": self.enlaces, "imagenes": self.imagenes,
        }


def _meta(soup, *, prop=None, name=None):
    etiqueta = soup.find("meta", attrs={"property": prop}) if prop else soup.find("meta", attrs={"name": name})
    return (etiqueta.get("content") or "").strip() if etiqueta else ""


def _fecha(soup):
    candidatos = [_meta(soup, prop="article:published_time"), _meta(soup, name="date")]
    t = soup.find("time")
    if t and t.get("datetime"):
        candidatos.append(t["datetime"])
    for c in candidatos:
        if not c:
            continue
        try:
            return datetime.fromisoformat(c.replace("Z", "+00:00"))
        except ValueError:
            continue
    return None


def _excluido(p):
    for padre in [p] + list(p.parents):
        clases = set(padre.get("class") or [])
        if clases & CLASES_EXCLUIDAS or padre.name in ("nav", "footer", "header"):
            return True
    return False


def extraer_documento(html, url, id_doc=None):
    soup = BeautifulSoup(html, "html.parser")
    contenedor = soup.find("article") or soup.find("main") or soup.body or soup

    titulo = _meta(soup, prop="og:title") or (soup.find("h1").get_text(strip=True) if soup.find("h1") else "") \
        or (soup.title.get_text(strip=True) if soup.title else "")
    sitio = _meta(soup, prop="og:site_name")
    canonica = soup.find("link", attrs={"rel": "canonical"})
    dominio = urlparse(canonica["href"]).netloc if canonica and canonica.get("href") else urlparse(url).netloc
    autor = _meta(soup, name="author")
    if not autor:
        span = soup.find(class_="autor")
        autor = span.get_text(strip=True) if span else ""

    parrafos = [p.get_text(" ", strip=True) for p in contenedor.find_all("p") if not _excluido(p)]
    parrafos = [p for p in parrafos if len(p) > 20]

    enlaces = []
    for a in contenedor.find_all("a", href=True):
        destino = urljoin(url, a["href"])
        if destino.startswith("http") and destino != url and destino not in enlaces:
            enlaces.append(destino)

    imagenes = []
    for img in contenedor.find_all("img", src=True):
        destino = urljoin(url, img["src"])
        if destino.startswith("http") and destino not in imagenes:
            imagenes.append(destino)

    return Documento(id=id_doc or url, url=url, titulo=titulo, sitio=sitio or dominio, dominio=dominio,
                     autor=autor, fecha=_fecha(soup), parrafos=parrafos, enlaces=enlaces, imagenes=imagenes)


def cargar_desde_archivo(ruta, url, id_doc=None):
    return extraer_documento(Path(ruta).read_text(encoding="utf-8"), url, id_doc)


class URLNoPermitida(ValueError):
    """La URL apunta a una red interna o usa un esquema no permitido."""


def _verificar_destino(url):
    """Bloquea esquemas distintos de http(s) y destinos privados (SSRF): loopback, redes internas,
    la dirección de metadatos de la nube (169.254.169.254) y similares. Comprueba TODAS las IPs del nombre."""
    import ipaddress
    import socket
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise URLNoPermitida(f"Solo se permiten URLs http(s): {url}")
    try:
        infos = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise URLNoPermitida(f"No se pudo resolver {p.hostname}")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if not ip.is_global or ip.is_multicast:
            raise URLNoPermitida(f"Destino no permitido (red interna): {p.hostname}")


class _RedireccionSegura(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _verificar_destino(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_ABRIDOR = urllib.request.build_opener(_RedireccionSegura)
MAX_BYTES_PAGINA = 3 * 1024 * 1024


def cargar_desde_url(url, id_doc=None, timeout=15):
    _verificar_destino(url)
    peticion = urllib.request.Request(url, headers={"User-Agent": "ECO/0.1 (laboratorio de defensa epistémica)"})
    with _ABRIDOR.open(peticion, timeout=timeout) as r:
        crudo = r.read(MAX_BYTES_PAGINA + 1)
        if len(crudo) > MAX_BYTES_PAGINA:
            raise URLNoPermitida(f"La página supera {MAX_BYTES_PAGINA // (1024 * 1024)} MB")
        html = crudo.decode(r.headers.get_content_charset() or "utf-8", errors="replace")
    return extraer_documento(html, url, id_doc)
