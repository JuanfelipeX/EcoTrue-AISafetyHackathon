#!/bin/bash
# Atajo: baja solo los audios del experimento (zip_remoto.py) y, si funciona, cancela la descarga completa.
cd /opt/voz
if /opt/voz/venv/bin/python /opt/voz/eco/deteccion_voz/zip_remoto.py --destino /opt/voz/itw > /opt/voz/zip.log 2>&1; then
  pkill -f "release_in_the_wild.zip" || true
  rm -f /opt/voz/itw.zip
  touch /opt/voz/LISTO
fi
