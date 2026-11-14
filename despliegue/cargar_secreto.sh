#!/bin/bash
# En la instancia: copia un parámetro cifrado de SSM a .env.servidor y reinicia ECO.
# Uso: bash despliegue/cargar_secreto.sh EXA_API_KEY /eco/exa_api_key
set -e
VAR="$1"; PARAM="$2"
cd /opt/eco
V=$(aws ssm get-parameter --region us-east-1 --name "$PARAM" --with-decryption --query Parameter.Value --output text)
grep -v "^$VAR=" .env.servidor > .env.tmp || true
echo "$VAR=$V" >> .env.tmp
mv .env.tmp .env.servidor && chmod 600 .env.servidor
docker compose up -d eco 2>&1 | tail -1
echo "$VAR cargada"
