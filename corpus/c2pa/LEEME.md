# PKI de demostración del laboratorio ECO

Certificados y claves **ficticios** para firmar las fotos sintéticas del mini-internet (mundos `*-c*`).
La CA raíz es "ECO Demo Root CA". Las claves privadas están aquí a propósito: no protegen nada real y
permiten regenerar el corpus. **No las use fuera de este laboratorio.**

En producción, ECO debe usar la lista oficial de confianza de C2PA (`ECO_C2PA_ANCLAS=/ruta/anclas.pem`)
y un sello de tiempo RFC 3161 en lugar de la fecha que declara el firmante.
