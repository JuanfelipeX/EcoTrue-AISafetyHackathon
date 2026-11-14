#!/bin/bash
# Corre el experimento cuando termina la preparación de la máquina y sube los resultados a S3.
# Uso: nohup bash deteccion_voz/correr.sh s3://bucket/prefijo &
DESTINO="$1"
while [ ! -f /opt/voz/LISTO ]; do sleep 15; done
cd /opt/voz/eco && git pull -q
/opt/voz/venv/bin/python deteccion_voz/experimento.py --raiz /opt/voz --salida /opt/voz/resultados > /opt/voz/exp.log 2>&1
aws s3 cp /opt/voz/resultados "$DESTINO/resultados" --recursive --region us-east-1 >> /opt/voz/exp.log 2>&1
aws s3 cp /opt/voz/exp.log "$DESTINO/exp.log" --region us-east-1
touch /opt/voz/TERMINADO
