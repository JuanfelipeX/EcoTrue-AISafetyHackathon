#!/bin/bash
# Prepara la máquina temporal de investigación de AASIST (Amazon Linux 2023). Se pasa como user-data.
# Instala Python, PyTorch (CPU), ffmpeg estático con Opus, clona AASIST y descarga In-the-Wild.
set -eux
dnf install -y python3.11 python3.11-pip git tar xz unzip
mkdir -p /opt/voz && cd /opt/voz
python3.11 -m venv venv
./venv/bin/pip install -q --upgrade pip
./venv/bin/pip install -q torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
./venv/bin/pip install -q numpy soundfile scipy
curl -sSL https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -o ffmpeg.tar.xz
tar -xf ffmpeg.tar.xz && cp ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/ && rm -rf ffmpeg-*-amd64-static ffmpeg.tar.xz
git clone -q https://github.com/clovaai/aasist.git
git clone -q https://github.com/SadidRomero77/eco.git
curl -sSL -o itw.zip https://huggingface.co/datasets/mueller91/In-The-Wild/resolve/main/release_in_the_wild.zip
unzip -q itw.zip -d itw && rm itw.zip
touch /opt/voz/LISTO
