#!/usr/bin/env bash
# Construye la imagen del runtime de reconocimientoFacial (M4).
#   bash deploy/docker/build.sh          # -> rfacerec:1
set -euo pipefail
cd "$(dirname "$0")"
IMG="${RF_IMAGE:-rfacerec:1}"
docker build -t "$IMG" .
echo "imagen construida: $IMG"
