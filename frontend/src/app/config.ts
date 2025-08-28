import { isDevMode } from '@angular/core';

export interface AppConfig {
  // API Endpoints
  backendUrl: string;
  localBackendUrl: string;
  devBackendUrl: string;
  photonUrl: string;
  
  // Map Services
  thunderforestApiKey: string;
  ostluftWmsUrl: string;
  
  // External Services
  openstreetmapUrl: string;
  arcgisUrl: string;
  opentopomapUrl: string;
  cartoUrl: string;
  
  // Contact Information
  contactEmail: string;
  githubUrl: string;
  researchPaperUrl: string;
  cossWebsiteUrl: string;
  
  // External Links
  photonGeocoderUrl: string;
  elasticsearchUrl: string;
  geoAdminUrl: string;
  greenRUrl: string;
  noiseMapUrl: string;
  iqairUrl: string;
  ostluftUrl: string;
  
  // Thunderforest URLs
  thunderforestBaseUrl: string;
  
  // Development
  isLocal: boolean;
  isDevMode: boolean;
}

// Configuration object with all static values
export const config: AppConfig = {
  // API Endpoints
  backendUrl: 'https://routify.ch/api/v2',
  localBackendUrl: 'http://localhost:8080',
  devBackendUrl: 'https://dev.routify.ch/api/v2',
  photonUrl: 'https://dev.routify.ch/photon/',
  
  // Map Services
  thunderforestApiKey: '7c80840849bd4b99a9dcd1372204947e',
  ostluftWmsUrl: 'https://ostluft.meteotest.ch/wms?',
  
  // External Services
  openstreetmapUrl: 'https://www.openstreetmap.org',
  arcgisUrl: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile',
  opentopomapUrl: 'https://tile.opentopomap.org',
  cartoUrl: 'https://{s}.basemaps.cartocdn.com/light_all',
  
  // Contact Information
  contactEmail: 'secretary-coss@coss.ethz.ch',
  githubUrl: 'https://github.com/ethz-coss/routify',
  researchPaperUrl: 'https://dl.acm.org/doi/10.1145/3640457.3691702',
  cossWebsiteUrl: 'https://coss.ethz.ch',
  
  // External Links
  photonGeocoderUrl: 'https://photon.komoot.io',
  elasticsearchUrl: 'https://www.elastic.co/elasticsearch',
  geoAdminUrl: 'https://api3.geo.admin.ch',
  greenRUrl: 'https://github.com/sachit27/greenR/',
  noiseMapUrl: 'https://data.geo.admin.ch/browser/index.html#/collections/ch.bafu.laerm-strassenlaerm_tag/items/laerm-strassenlaerm_tag?.language=en',
  iqairUrl: 'https://www.iqair.com/',
  ostluftUrl: 'https://www.ostluft.ch/',
  
  // Thunderforest URLs
  thunderforestBaseUrl: 'https://tile.thunderforest.com',
  
  // Development - using the same detection logic as before
  isLocal: false, // This will be toggled by the backend service
  isDevMode: isDevMode() || ['localhost', '127.0.0.1', 'dev.routify.ch'].includes(window.location.hostname)
};
