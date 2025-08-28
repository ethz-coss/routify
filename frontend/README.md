
# Routify Frontend

Routify Frontend is an Angular web application that provides a rich UI for the Routify routing engine (served by the Routify Backend). It offers interactive route planning, map overlays, and analysis tools for air quality, elevation, noise, and more.

## Prerequisites

- Node.js LTS (recommended)
- npm (bundled with Node.js)
- Angular CLI installed globally

```bash
npm install -g @angular/cli
```

You can verify your environment with:

```bash
ng version
```

The project targets Angular 17.

## Installation

```bash
git clone <your-repo-url>
cd frontend
npm install
```

## Configuration

Application settings live in `src/app/config.ts`. Key fields include:

```typescript
// API Endpoints
backendUrl: 'https://routify.ch/api/v2',        // Production backend
localBackendUrl: 'http://localhost:8080',       // Local development backend
devBackendUrl: 'https://dev.routify.ch/api/v2', // Development backend

// Geocoding
photonUrl: 'https://dev.routify.ch/photon/'
```

To point the frontend at a different backend, adjust the URLs above. No environment files are required; configuration is centralized in this file.

## Running locally (development)

1. Start the Routify Backend locally (default: `http://localhost:8080`).
2. Start the frontend dev server:

```bash
npm start
# or
ng serve
```

3. Open `http://localhost:4200` in your browser.

## Production build

Build the optimized production bundle:

```bash
npm run build
# or
ng build
```

The output will be written to `dist/`.

### Version metadata (prebuild)

This project includes a prebuild step that generates version metadata used by the UI:

```json
scripts: {
  "prebuild": "node scripts/generate-version.js"
}
```

What it does:
- Runs before `npm run build`.
- Creates `src/assets/version.json` with:
  - `version`: from `package.json`.
  - `gitHash`: short commit hash (`git rev-parse --short HEAD`).
  - `buildDate`: ISO timestamp of the build.

Source: `scripts/generate-version.js`. The app can display this info (e.g., in an About dialog) by fetching `/assets/version.json` at runtime.

## Short introduction to Routify

Routify is a research-driven routing system that enables multi-criteria route planning. The frontend visualizes routes and overlays contextual datasets (e.g., air quality, elevation, noise) to help users choose routes beyond shortest-time. It integrates search/autocomplete, map interactions, and route analyses.

## Used technologies and main libraries

- Angular 17, Angular CLI
- RxJS, TypeScript
- Angular Material (`@angular/material`, `@angular/cdk`)
- Leaflet for web mapping, plus plugins:
  - `leaflet-groupedlayercontrol`
  - `leaflet-compass`
  - `leaflet-rotate`
  - `leaflet-maskcanvas`
- Charts: `ng-apexcharts` (pinned to `1.7.6` for Angular 17 compatibility) and `apexcharts`
- UI components: `@ng-select/ng-select`
- Geospatial utilities: `proj4`, `proj4leaflet`
- UX helpers: `sweetalert2`

## Common scripts

```json
{
  "start": "ng serve",
  "build": "ng build",
  "test": "ng test"
}
```

## Troubleshooting

- On install conflicts, try: `npm install --legacy-peer-deps`.
- If you change map-related assets or configs, restart the dev server to ensure Leaflet layers reload correctly.
