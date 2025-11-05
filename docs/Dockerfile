FROM alpine:3.20 AS build

RUN apk add --no-cache doxygen graphviz curl tar nodejs npm chromium
RUN npm install -g @mermaid-js/mermaid-cli
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser

WORKDIR /work

# fetch doxygen-awesome assets
RUN curl -fsSL https://github.com/jothepro/doxygen-awesome-css/archive/refs/heads/main.tar.gz \
    | tar -xz && mv doxygen-awesome-css-main /tmp/doxygen-awesome-css

COPY README.md ./README.md
COPY docs/Doxyfile ./Doxyfile
COPY docs/doxygen-assets-install.sh ./doxygen-assets-install.sh
RUN chmod +x doxygen-assets-install.sh && ./doxygen-assets-install.sh
COPY backend /src/backend
COPY frontend /src/frontend

RUN doxygen Doxyfile

FROM nginx:alpine

COPY --from=build /work/output/html /usr/share/nginx/html

EXPOSE 80
