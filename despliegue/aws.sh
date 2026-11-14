#!/usr/bin/env bash
# Despliegue de ECO en AWS: una instancia EC2 con Docker + túnel de Cloudflare (sin puertos abiertos).
#
#   bash despliegue/aws.sh crear        crea rol, parámetro del token, grupo de seguridad e instancia
#   bash despliegue/aws.sh actualizar   en la instancia: git pull + docker compose up --build (vía SSM)
#   bash despliegue/aws.sh estado       muestra la instancia y la salud del servicio
#   bash despliegue/aws.sh borrar       termina la instancia y borra rol, perfil, parámetro y grupo
#
# Requisitos: AWS CLI con credenciales, y CLOUDFLARE_TUNNEL_TOKEN en .env (nunca se imprime ni va a git).
# Seguridad: el grupo de seguridad no abre ningún puerto de entrada; la administración es por SSM.
# El rol de la instancia solo puede invocar modelos de Anthropic en Bedrock y leer /eco/*.
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
NOMBRE="eco-hackathon"
REPO="https://github.com/SadidRomero77/eco.git"
TIPO="${ECO_TIPO_INSTANCIA:-t3.medium}"
PARAM="/eco/cloudflare_tunnel_token"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
aws_() { aws --region "$REGION" --output text "$@"; }

instancia() {
  aws_ ec2 describe-instances --filters "Name=tag:Name,Values=$NOMBRE" \
    "Name=instance-state-name,Values=pending,running,stopping,stopped" \
    --query "Reservations[].Instances[].InstanceId" | head -1
}

crear() {
  local cuenta; cuenta=$(aws_ sts get-caller-identity --query Account)

  echo "1/5 Rol de la instancia ($NOMBRE)…"
  if ! aws_ iam get-role --role-name "$NOMBRE" >/dev/null 2>&1; then
    aws_ iam create-role --role-name "$NOMBRE" --assume-role-policy-document \
      '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
    aws_ iam attach-role-policy --role-name "$NOMBRE" --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
  fi
  aws_ iam put-role-policy --role-name "$NOMBRE" --policy-name eco-minimo --policy-document "{
    \"Version\":\"2012-10-17\",\"Statement\":[
      {\"Effect\":\"Allow\",\"Action\":[\"bedrock:InvokeModel\",\"bedrock:InvokeModelWithResponseStream\"],
       \"Resource\":[\"arn:aws:bedrock:*::foundation-model/anthropic.*\",\"arn:aws:bedrock:*:$cuenta:inference-profile/us.anthropic.*\"]},
      {\"Effect\":\"Allow\",\"Action\":[\"ssm:GetParameter\"],\"Resource\":\"arn:aws:ssm:$REGION:$cuenta:parameter/eco/*\"}]}"
  if ! aws_ iam get-instance-profile --instance-profile-name "$NOMBRE" >/dev/null 2>&1; then
    aws_ iam create-instance-profile --instance-profile-name "$NOMBRE" >/dev/null
    aws_ iam add-role-to-instance-profile --instance-profile-name "$NOMBRE" --role-name "$NOMBRE"
    sleep 10  # IAM tarda en propagar el perfil
  fi

  echo "2/5 Token del túnel en SSM Parameter Store (cifrado)…"
  local token; token=$(grep -E '^CLOUDFLARE_TUNNEL_TOKEN=' "$RAIZ/.env" | head -1 | cut -d= -f2- | tr -d '"' | sed 's/.*--token[[:space:]]*//')
  [ -n "$token" ] || { echo "Falta CLOUDFLARE_TUNNEL_TOKEN en .env"; exit 1; }
  aws_ ssm put-parameter --name "$PARAM" --type SecureString --overwrite --value "$token" >/dev/null

  echo "3/5 Grupo de seguridad sin puertos de entrada…"
  local vpc sg
  vpc=$(aws_ ec2 describe-vpcs --filters Name=is-default,Values=true --query "Vpcs[0].VpcId")
  sg=$(aws_ ec2 describe-security-groups --filters "Name=group-name,Values=$NOMBRE" "Name=vpc-id,Values=$vpc" \
       --query "SecurityGroups[0].GroupId" 2>/dev/null || true)
  if [ -z "$sg" ] || [ "$sg" = "None" ]; then
    sg=$(aws_ ec2 create-security-group --group-name "$NOMBRE" --vpc-id "$vpc" \
         --description "ECO: sin entrada; salida para Cloudflare Tunnel, Bedrock y GitHub" --query GroupId)
  fi

  if [ -n "$(instancia)" ]; then echo "Ya existe la instancia $(instancia). Use 'actualizar'."; return; fi

  echo "4/5 Instancia $TIPO (Amazon Linux 2023)…"
  local ami; ami=$(aws_ ssm get-parameter --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 --query Parameter.Value)
  local datos; datos=$(mktemp)
  cat > "$datos" <<USERDATA
#!/bin/bash
set -eux
dnf install -y docker git
mkdir -p /usr/local/lib/docker/cli-plugins
curl -sSL https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-x86_64 -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
systemctl enable --now docker
git clone $REPO /opt/eco
cd /opt/eco
cp despliegue/servidor.env.ejemplo .env.servidor
TOKEN=\$(aws ssm get-parameter --region $REGION --name $PARAM --with-decryption --query Parameter.Value --output text)
sed -i "s|^TUNNEL_TOKEN=.*|TUNNEL_TOKEN=\$TOKEN|" .env.servidor
chmod 600 .env.servidor
docker compose up -d --build
USERDATA
  local id
  id=$(aws_ ec2 run-instances --image-id "$ami" --instance-type "$TIPO" \
       --iam-instance-profile Name="$NOMBRE" --security-group-ids "$sg" \
       --metadata-options HttpTokens=required,HttpPutResponseHopLimit=2,HttpEndpoint=enabled \
       --block-device-mappings 'DeviceName=/dev/xvda,Ebs={VolumeSize=20,VolumeType=gp3,Encrypted=true}' \
       --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NOMBRE},{Key=proyecto,Value=eco}]" \
       --user-data "file://$(command -v cygpath >/dev/null && cygpath -m "$datos" || echo "$datos")" --query "Instances[0].InstanceId")
  rm -f "$datos"
  echo "5/5 Instancia $id creada. Arranque + build de la imagen tardan ~4 minutos."
  echo "Seguimiento: bash despliegue/aws.sh estado"
}

en_instancia() {
  local id; id=$(instancia); [ -n "$id" ] || { echo "No hay instancia"; exit 1; }
  local cmd; cmd=$(aws_ ssm send-command --instance-ids "$id" --document-name AWS-RunShellScript \
        --parameters "commands=[\"$1\"]" --query Command.CommandId)
  aws --region "$REGION" ssm wait command-executed --command-id "$cmd" --instance-id "$id" || true
  aws_ ssm get-command-invocation --command-id "$cmd" --instance-id "$id" \
    --query "[Status,StandardOutputContent,StandardErrorContent]"
}

case "${1:-}" in
  crear) crear ;;
  actualizar) en_instancia "cd /opt/eco && git pull --ff-only && docker compose up -d --build 2>&1 | tail -5 && docker compose ps" ;;
  estado)
    aws_ ec2 describe-instances --filters "Name=tag:Name,Values=$NOMBRE" \
      --query "Reservations[].Instances[].[InstanceId,InstanceType,State.Name,LaunchTime]"
    en_instancia "cd /opt/eco && docker compose ps && curl -s localhost:8765/api/salud || true" ;;
  borrar)
    id=$(instancia); [ -n "$id" ] && aws_ ec2 terminate-instances --instance-ids "$id" >/dev/null && \
      aws --region "$REGION" ec2 wait instance-terminated --instance-ids "$id"
    aws_ ssm delete-parameter --name "$PARAM" 2>/dev/null || true
    aws_ iam remove-role-from-instance-profile --instance-profile-name "$NOMBRE" --role-name "$NOMBRE" 2>/dev/null || true
    aws_ iam delete-instance-profile --instance-profile-name "$NOMBRE" 2>/dev/null || true
    aws_ iam delete-role-policy --role-name "$NOMBRE" --policy-name eco-minimo 2>/dev/null || true
    aws_ iam detach-role-policy --role-name "$NOMBRE" --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore 2>/dev/null || true
    aws_ iam delete-role --role-name "$NOMBRE" 2>/dev/null || true
    sg=$(aws_ ec2 describe-security-groups --filters "Name=group-name,Values=$NOMBRE" --query "SecurityGroups[0].GroupId" 2>/dev/null || true)
    [ -n "$sg" ] && [ "$sg" != "None" ] && aws_ ec2 delete-security-group --group-id "$sg" || true
    echo "Recursos de ECO borrados." ;;
  *) sed -n 2,12p "$0" ;;
esac
