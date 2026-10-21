#!/usr/bin/env bash
# Despliega las dos instancias desde el mismo `main`:
#   1. laboral (mail) con deploy_prod.sh
#   2. personal (liveyourdre2) con deploy_ojos.sh
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
bash "$DIR/deploy/deploy_prod.sh" "$@"
bash "$DIR/deploy/ojos/deploy_ojos.sh"
