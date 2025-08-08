# Minimaler Python-Basiscontainer
FROM python:3.11-slim

# PlatformIO Cache persistent
ENV PLATFORMIO_CORE_DIR=/data/cache/.platformio

# Systempakete für ESPHome/PlatformIO
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    bash \
    libffi-dev \
    libusb-1.0-0-dev \
    libssl-dev \
    unzip \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Python-Abhängigkeiten inkl. ESPHome
RUN pip install --no-cache-dir \
    esphome \
    flask \
    flask-cors

# Add-on Arbeitsverzeichnis
WORKDIR /app

# Kopiere Flask-Server und Webinterface
COPY server.py /app/server.py
COPY www /app/www

# Lege Firmware-Ausgabeordner an
RUN mkdir -p /app/www/firmware

# Stelle sicher: esphome ist im PATH (optional)
ENV PATH="/root/.local/bin:$PATH"

# Offenlegung des Ports für WebUI
EXPOSE 8099

# Starte Flask-Server direkt
CMD ["python3", "/app/server.py"]
