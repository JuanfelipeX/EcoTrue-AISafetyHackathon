"""
Mundos con fotos firmadas (C2PA) para evaluar la señal de procedencia de ECO.

Todo es sintético: las fotos son dibujos generados aquí y los certificados salen de una CA de demostración
("ECO Demo Root CA") guardada en corpus/c2pa/. Esas claves solo sirven para este laboratorio.

Tipos de mundo (conjunto "procedencia"):
  foto_firmada_parafrasis   El ataque abierto de ECO (copias reescritas con detalles inventados), pero las copias
                            reutilizan la foto firmada por el medio de origen, con su manifiesto intacto.
  foto_sin_metadatos        Igual, pero las copias recomprimen la foto (como al reenviarla por WhatsApp):
                            el manifiesto desaparece y solo queda la huella visual.
  fecha_falsa               Paráfrasis donde una copia declara una fecha anterior al origen, pero usa la foto
                            que el origen firmó después de esa fecha.
  organico_con_fotos        Cobertura independiente: cada medio firma su propia foto; dos medios usan además la
                            misma foto de agencia; una página trae una ilustración declarada como IA y otra una
                            foto alterada después de firmarse. Nada de esto debe juntar medios independientes.
"""

import datetime as dt
import io
import json
import random
import re
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

DIR_PKI = Path(__file__).resolve().parent / "c2pa"
AGENCIA = "Agencia Andina de Imágenes"
TIPOS_PROCEDENCIA = ["foto_firmada_parafrasis", "foto_sin_metadatos", "fecha_falsa", "organico_con_fotos"]
BASE_DE = {"foto_firmada_parafrasis": "fabricado_parafrasis", "foto_sin_metadatos": "fabricado_parafrasis",
           "fecha_falsa": "parafrasis", "organico_con_fotos": "organico"}
FUENTE = "http://cv.iptc.org/newscodes/digitalsourcetype/"


# ---------------------------------------------------------------------------
# PKI de demostración
# ---------------------------------------------------------------------------
def _slug(texto):
    return re.sub(r"[^a-z0-9]+", "-", texto.lower().encode("ascii", "ignore").decode()).strip("-")


def _ca():
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    DIR_PKI.mkdir(parents=True, exist_ok=True)
    ruta_cert, ruta_clave = DIR_PKI / "ca.pem", DIR_PKI / "ca_clave_DEMO.pem"
    if ruta_cert.exists() and ruta_clave.exists():
        return (x509.load_pem_x509_certificate(ruta_cert.read_bytes()),
                serialization.load_pem_private_key(ruta_clave.read_bytes(), None))
    ahora = dt.datetime.now(dt.timezone.utc)
    clave = ec.generate_private_key(ec.SECP256R1())
    nombre = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "ECO Demo Root CA"),
                        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ECO laboratorio (solo demostración)"),
                        x509.NameAttribute(NameOID.COUNTRY_NAME, "CO")])
    cert = (x509.CertificateBuilder().subject_name(nombre).issuer_name(nombre).public_key(clave.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(ahora - dt.timedelta(days=1))
            .not_valid_after(ahora + dt.timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=False, content_commitment=False, key_encipherment=False,
                                         data_encipherment=False, key_agreement=False, key_cert_sign=True,
                                         crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(clave.public_key()), critical=False)
            .sign(clave, hashes.SHA256()))
    ruta_cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    ruta_clave.write_bytes(clave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                               serialization.NoEncryption()))
    return cert, clave


def firmante(nombre_medio):
    """(cadena PEM, clave PEM) del medio; se crean una vez y se reutilizan."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    carpeta = DIR_PKI / "firmantes"
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta_cert, ruta_clave = carpeta / f"{_slug(nombre_medio)}.pem", carpeta / f"{_slug(nombre_medio)}_clave_DEMO.pem"
    ca_cert, ca_clave = _ca()
    ca_pem = ca_cert.public_bytes(serialization.Encoding.PEM)
    if ruta_cert.exists() and ruta_clave.exists():
        return ruta_cert.read_bytes() + ca_pem, ruta_clave.read_bytes()
    ahora = dt.datetime.now(dt.timezone.utc)
    clave = ec.generate_private_key(ec.SECP256R1())
    nombre = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, nombre_medio),
                        x509.NameAttribute(NameOID.ORGANIZATION_NAME, nombre_medio),
                        x509.NameAttribute(NameOID.COUNTRY_NAME, "CO")])
    cert = (x509.CertificateBuilder().subject_name(nombre).issuer_name(ca_cert.subject).public_key(clave.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(ahora - dt.timedelta(days=1))
            .not_valid_after(ahora + dt.timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=False,
                                         data_encipherment=False, key_agreement=False, key_cert_sign=False,
                                         crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.EMAIL_PROTECTION]), critical=False)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(clave.public_key()), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_clave.public_key()), critical=False)
            .sign(ca_clave, hashes.SHA256()))
    ruta_cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    ruta_clave.write_bytes(clave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                               serialization.NoEncryption()))
    return ruta_cert.read_bytes() + ca_pem, ruta_clave.read_bytes()


# ---------------------------------------------------------------------------
# Fotos sintéticas y firma
# ---------------------------------------------------------------------------
def foto(rng, ia=False):
    """Un 'paisaje' abstracto y distinto en cada llamada (no representa a nadie real)."""
    w, h = 640, 400
    cielo = tuple(rng.randint(60, 200) for _ in range(3))
    img = Image.new("RGB", (w, h), cielo)
    d = ImageDraw.Draw(img)
    for _ in range(rng.randint(5, 9)):
        x, y = rng.randint(-80, w), rng.randint(h // 3, h)
        d.rectangle([x, y, x + rng.randint(60, 220), h], fill=tuple(rng.randint(20, 230) for _ in range(3)))
    for _ in range(rng.randint(2, 4)):
        x, y, r = rng.randint(0, w), rng.randint(0, h // 2), rng.randint(15, 60)
        d.ellipse([x - r, y - r, x + r, y + r], fill=tuple(rng.randint(150, 255) for _ in range(3)))
    if ia:
        for i in range(0, w, 16):
            d.line([(i, 0), (w - i, h)], fill=(255, 0, 255), width=1)
    etiqueta = "Ilustración generada con IA (sintética)" if ia else "Foto sintética · laboratorio ECO"
    d.rectangle([0, h - 26, w, h], fill=(0, 0, 0))
    d.text((10, h - 20), etiqueta, fill=(255, 255, 255))
    buffer = io.BytesIO()
    img.save(buffer, "JPEG", quality=88)
    return buffer.getvalue()


def firmar(jpeg, nombre_medio, fecha_iso, titulo, ia=False):
    import c2pa
    cadena, clave = firmante(nombre_medio)
    fuente = "trainedAlgorithmicMedia" if ia else "digitalCapture"
    manifiesto = {
        "claim_generator_info": [{"name": "ECO laboratorio", "version": "1.0"}],
        "title": titulo,
        "format": "image/jpeg",
        "assertions": [
            {"label": "c2pa.actions", "data": {"actions": [{"action": "c2pa.created", "digitalSourceType": FUENTE + fuente}]}},
            {"label": "org.eco.publicacion", "data": {"medio": nombre_medio, "fecha": fecha_iso}},
        ],
    }
    info = c2pa.C2paSignerInfo(c2pa.C2paSigningAlg.ES256, cadena, clave, None)
    with tempfile.TemporaryDirectory() as tmp:
        origen, destino = Path(tmp) / "o.jpg", Path(tmp) / "f.jpg"
        origen.write_bytes(jpeg)
        with c2pa.Signer.from_info(info) as signer, c2pa.Builder(json.dumps(manifiesto)) as b:
            b.sign_file(origen, destino, signer)
        return destino.read_bytes()


def recomprimir(jpeg):
    """Lo que hace un reenvío: reescala y recomprime; el manifiesto C2PA se pierde."""
    img = Image.open(io.BytesIO(jpeg)).convert("RGB")
    img = img.resize((int(img.width * 0.9), int(img.height * 0.9)))
    buffer = io.BytesIO()
    img.save(buffer, "JPEG", quality=72)
    return buffer.getvalue()


def alterar(jpeg_firmado):
    """Cambia un byte de los datos de imagen después de firmar: la firma queda rota."""
    datos = bytearray(jpeg_firmado)
    datos[-300] ^= 0x5A
    return bytes(datos)


def _iso(fecha):
    return fecha.strftime("%Y-%m-%dT%H:%M:00-05:00")


# ---------------------------------------------------------------------------
# Decoración de un mundo (se llama desde construir_escenario, antes de escribir las páginas)
# ---------------------------------------------------------------------------
def decorador(tipo, rng):
    def decorar(paginas, carpeta):
        dir_img = carpeta / "img"
        dir_img.mkdir(exist_ok=True)

        def guardar(nombre, datos):
            (dir_img / nombre).write_bytes(datos)
            return f"img/{nombre}"

        ordenadas = sorted(paginas, key=lambda p: p["fecha"])
        if tipo == "organico_con_fotos":
            t_agencia = ordenadas[0]["fecha"] - dt.timedelta(minutes=40)
            agencia = firmar(foto(rng), AGENCIA, _iso(t_agencia), "Foto de agencia")
            con_agencia = {p["id"] for p in rng.sample(ordenadas, 2)}
            ia_en = rng.choice(ordenadas)["id"]
            rota_en = rng.choice([p for p in ordenadas if p["id"] != ia_en])["id"]
            for p in ordenadas:
                medio = p["medio"]["nombre"]
                propia = firmar(foto(rng), medio, _iso(p["fecha"]), p["titulo"])
                if p["id"] == rota_en:
                    propia = alterar(propia)
                figuras = [{"src": guardar(f"{p['id']}-1.jpg", propia), "pie": f"Foto: {medio}"}]
                if p["id"] in con_agencia:
                    figuras.append({"src": guardar(f"{p['id']}-agencia.jpg", agencia), "pie": f"Foto: {AGENCIA}"})
                if p["id"] == ia_en:
                    ilustracion = firmar(foto(rng, ia=True), medio, _iso(p["fecha"]), "Ilustración", ia=True)
                    figuras.append({"src": guardar(f"{p['id']}-ia.jpg", ilustracion),
                                    "pie": f"Ilustración generada con IA · {medio}"})
                p["figuras"] = figuras
            return

        origen = next(p for p in ordenadas if p["rol"] == "origen")
        medio_origen = origen["medio"]["nombre"]
        if tipo == "fecha_falsa":
            copia = rng.choice([p for p in ordenadas if p["rol"] != "origen"])
            copia["fecha"] = origen["fecha"] - dt.timedelta(minutes=rng.randint(30, 90))
            copia["rol"] = "copia_con_fecha_falsa"
        firmada = firmar(foto(rng), medio_origen, _iso(origen["fecha"]), origen["titulo"])
        sin_meta = recomprimir(firmada)
        for p in ordenadas:
            if p is origen:
                datos = firmada
            elif tipo == "foto_sin_metadatos":
                datos = sin_meta
            else:
                datos = firmada
            p["figuras"] = [{"src": guardar(f"{p['id']}-1.jpg", datos), "pie": f"Foto: {medio_origen}"
                             if p is origen else "Foto: archivo"}]
    return decorar


def generar_mundos(eventos, construir_escenario, t_base, semilla):
    rng = random.Random(semilla + 3000)
    escenarios = []
    for n_ev, ev in enumerate(eventos):
        tipos = TIPOS_PROCEDENCIA[:]
        rng.shuffle(tipos)
        for s, tipo in enumerate(tipos, start=1):
            esc_id = f"{ev['id']}-c{s}"
            t0 = t_base + timedelta_dias(90 + n_ev * 5 + s, rng.randint(0, 600))
            esc = construir_escenario(ev, esc_id, BASE_DE[tipo], rng, t0, decorar=decorador(tipo, rng))
            esc["tipo"] = tipo
            esc["conjunto"] = "procedencia"
            escenarios.append(esc)
    return escenarios


def timedelta_dias(dias, minutos):
    return dt.timedelta(days=dias, minutes=minutos)
