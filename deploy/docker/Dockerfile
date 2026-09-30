# Runtime de reconocimientoFacial para el pool de SuperServer (M4).
#
# Imagen portable (funciona en nodos con glibc/kernel antiguos: solo necesita un
# Docker que arranque; todas las dependencias viven dentro).
#
# El código del proyecto y los modelos NO van dentro de la imagen: se montan en
# solo lectura desde el nodo (`/app`), y el sandbox efímero en `/work`.
#
#   docker run --rm --network=none \
#     -v /opt/taildeck/reconocimientoFacial:/app:ro \
#     -v /run/taildeck/jobs/<id>:/work \
#     -w /work rfacerec:1 \
#     python /app/motor/procesa_video_pool.py ...
FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# build-essential: insightface (0.7.3) compila extensión Cython en el install.
# libgomp1: OpenMP que necesitan onnxruntime/OpenVINO y scipy.
# patchelf: limpia el flag de stack ejecutable del .so de onnxruntime (ver abajo).
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libgomp1 patchelf \
 && rm -rf /var/lib/apt/lists/*

COPY requirements-runtime.txt /tmp/requirements-runtime.txt
RUN pip install -r /tmp/requirements-runtime.txt

# onnxruntime-openvino trae el flag PT_GNU_STACK ejecutable; glibc >= 2.34 lo
# rechaza al cargar ("cannot enable executable stack as shared object requires").
# El flag es innecesario: se limpia en el binario.
RUN patchelf --clear-execstack /usr/local/lib/python3.10/site-packages/onnxruntime/capi/*.so

# Ya no se necesita el compilador en runtime; se retira para reducir tamaño.
RUN apt-get purge -y build-essential patchelf && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /work
CMD ["python", "-V"]
