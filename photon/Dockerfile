# Photon geocoder service
FROM eclipse-temurin:17-jdk

ENV PHOTON_VERSION=0.7.0

# Install curl and wget
RUN apt-get update && apt-get install -y curl wget ca-certificates --no-install-recommends && rm -rf /var/lib/apt/lists/*

# Download Photon JAR
RUN mkdir -p /photon && \
    wget -O /photon/photon-${PHOTON_VERSION}.jar https://github.com/komoot/photon/releases/download/${PHOTON_VERSION}/photon-${PHOTON_VERSION}.jar

EXPOSE 2322

# Create startup script that waits for Nominatim and initializes Photon
RUN cat <<'EOF' > /start-photon.sh
#!/bin/bash
set -euo pipefail

echo "Waiting for Nominatim database port..."
while ! nc -z nominatim 5432; do
  sleep 1
done

echo "Waiting for Nominatim HTTP status..."
until curl -fs http://nominatim:8080/status >/dev/null; do
  sleep 5
done

echo "Creating Photon index..."
until java -jar /photon/photon-${PHOTON_VERSION}.jar -host nominatim -database nominatim -user nominatim -password password -nominatim-import; do
  echo "Photon index import failed, retrying in 10s..."
  sleep 10
done

echo "Starting Photon server..."
exec java -jar /photon/photon-${PHOTON_VERSION}.jar -listen-port 2322 -host nominatim -database nominatim -user nominatim -password password
EOF
RUN chmod +x /start-photon.sh

# Install netcat for connection testing
RUN apt-get update && apt-get install -y netcat-openbsd && rm -rf /var/lib/apt/lists/*

CMD ["/start-photon.sh"]
