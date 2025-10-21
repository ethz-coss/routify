# Photon geocoder service
FROM openjdk:17-jdk-slim

ENV PHOTON_VERSION=0.7.0

# Install curl and wget
RUN apt-get update && apt-get install -y curl wget && rm -rf /var/lib/apt/lists/*

# Download Photon JAR
RUN mkdir -p /photon && \
    wget -O /photon/photon-${PHOTON_VERSION}.jar https://github.com/komoot/photon/releases/download/${PHOTON_VERSION}/photon-${PHOTON_VERSION}.jar

EXPOSE 2322

# Create startup script that creates index first
RUN echo '#!/bin/bash' > /start-photon.sh && \
    echo 'echo "Waiting for Nominatim to be ready..."' >> /start-photon.sh && \
    echo 'while ! nc -z nominatim 5432; do sleep 1; done' >> /start-photon.sh && \
    echo 'echo "Creating Photon index..."' >> /start-photon.sh && \
    echo 'java -jar /photon/photon-0.7.0.jar -host nominatim -database nominatim -user nominatim -password password -nominatim-import' >> /start-photon.sh && \
    echo 'echo "Starting Photon server..."' >> /start-photon.sh && \
    echo 'java -jar /photon/photon-0.7.0.jar -listen-port 2322 -host nominatim -database nominatim -user nominatim -password password' >> /start-photon.sh && \
    chmod +x /start-photon.sh

# Install netcat for connection testing
RUN apt-get update && apt-get install -y netcat-openbsd && rm -rf /var/lib/apt/lists/*

CMD ["/start-photon.sh"]

