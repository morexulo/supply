#!/usr/bin/env bash
# scripts/run_streamlit.sh
# Lanza la app Streamlit asegurando entorno y rutas correctas

set -eo pipefail

# 1. Ir a la raíz del proyecto
cd "$(dirname "$0")/.." || exit 1

# 2. Activar entorno virtual si existe
if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
  echo "Entorno virtual activado (.venv)"
fi

# 3. Asegurar que Python vea el paquete src/
export PYTHONPATH="$(pwd):${PYTHONPATH:-}"
echo "PYTHONPATH: $PYTHONPATH"

# 4. Mostrar info y ejecutar
echo "Ejecutando Streamlit desde raíz: $(pwd)"
echo "Archivo: src/app/streamlit_app.py"

# 5. Lanzar Streamlit
streamlit run src/app/streamlit_app.py

