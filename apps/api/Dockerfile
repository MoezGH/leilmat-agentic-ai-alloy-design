FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git \
    # X11 runtime libraries needed by taichi 1.7+.  Taichi's compiled
    # extension dynamically links against libX11/libXrender/libGLU
    # even when running headlessly on CPU (GLFW is statically linked at
    # build time).  python:3.11-slim strips these by default — without
    # them ``import taichi`` raises ``ImportError: libX11.so.6: cannot
    # open shared object file`` and the Sprint 2.6 anisotropic KWC
    # simulator is unavailable.
    libx11-6 libxrender1 libxext6 libxcursor1 libxinerama1 libxi6 libxrandr2 \
    libglu1-mesa libgomp1 libxxf86vm1 \
    && rm -rf /var/lib/apt/lists/*
# Note: wget previously installed here for healthcheck use is now redundant
# because docker-compose.prod.yml's api healthcheck switched to python urllib
# (commit cd4c69f).  Keeping git installed because some pip dependencies build
# from VCS sources during install.

COPY apps/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
