import * as L from 'leaflet'
import { config } from '../config'

// declaration of available tile layers
export const baseLayers: any = {
    'OpenStreetMap' : new L.TileLayer(
        'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', 
        {
            maxZoom: 19,
            minZoom: 3,
            attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        }
    ),
    'Satellite imagery' : new L.TileLayer(
        `${config.arcgisUrl}/{z}/{y}/{x}`,
        {
            maxZoom: 21,
            minZoom: 3,
            attribution: '&copy; <a href="https://services.arcgisonline.com/arcgis/">ArcGIS Services</a>'
        }
    ),
    'Topography' : new L.TileLayer(
        `${config.opentopomapUrl}/{z}/{x}/{y}.png.png`, 
        {
            maxZoom: 16,
            minZoom: 3,
            attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        }
    ),
    'Transport Dark' : new L.TileLayer(
        `${config.thunderforestBaseUrl}/transport-dark/{z}/{x}/{y}.png?apikey=${config.thunderforestApiKey}`, 
        {
            maxZoom: 16,
            minZoom: 3,
            attribution: '&copy; <a href="https://manage.thunderforest.com/dashboard">Thunderforest</a>'
        }
    ),
    'Outdoors' : new L.TileLayer(
        `${config.thunderforestBaseUrl}/outdoors/{z}/{x}/{y}.png?apikey=${config.thunderforestApiKey}`, 
        {
            maxZoom: 16,
            minZoom: 3,
            attribution: '&copy; <a href="https://manage.thunderforest.com/dashboard">Thunderforest</a>'
        }
    ),
    'OpenCycleMap' : new L.TileLayer(
        `${config.thunderforestBaseUrl}/cycle/{z}/{x}/{y}.png?apikey=${config.thunderforestApiKey}`, 
        {
            maxZoom: 16,
            minZoom: 3,
            attribution: '&copy; <a href="https://manage.thunderforest.com/dashboard">Thunderforest</a>'
        }
    ),
    'Transport' : new L.TileLayer(
        `${config.thunderforestBaseUrl}/transport/{z}/{x}/{y}.png?apikey=${config.thunderforestApiKey}`, 
        {
            maxZoom: 16,
            minZoom: 3,
            attribution: '&copy; <a href="https://manage.thunderforest.com/dashboard">Thunderforest</a>'
        }
    ),
    'Pioneer' : new L.TileLayer(
        `${config.thunderforestBaseUrl}/pioneer/{z}/{x}/{y}.png?apikey=${config.thunderforestApiKey}`, 
        {
            maxZoom: 16,
            minZoom: 3,
            attribution: '&copy; <a href="https://manage.thunderforest.com/dashboard">Thunderforest</a>'
        }
    ),
    'Mobile Atlas' : new L.TileLayer(
        `${config.thunderforestBaseUrl}/mobile-atlas/{z}/{x}/{y}.png?apikey=${config.thunderforestApiKey}`, 
        {
            maxZoom: 16,
            minZoom: 3,
            attribution: '&copy; <a href="https://manage.thunderforest.com/dashboard">Thunderforest</a>'
        }
    ),
    'Landscape' : new L.TileLayer(
        `${config.thunderforestBaseUrl}/landscape/{z}/{x}/{y}.png?apikey=${config.thunderforestApiKey}`, 
        {
            maxZoom: 16,
            minZoom: 3,
            attribution: '&copy; <a href="https://manage.thunderforest.com/dashboard">Thunderforest</a>'
        }
    ),
    'Neighbourhood' : new L.TileLayer(
        `${config.thunderforestBaseUrl}/neighbourhood/{z}/{x}/{y}.png?apikey=${config.thunderforestApiKey}`, 
        {
            maxZoom: 16,
            minZoom: 3,
            attribution: '&copy; <a href="https://manage.thunderforest.com/dashboard">Thunderforest</a>'
        }
    ),
    'Positron' : new L.TileLayer(
        `${config.cartoUrl}/{z}/{x}/{y}{r}.png`,
        {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
            subdomains: 'abcd',
            maxZoom: 20
        }
    )
}

// declaration of available overlay layers
export const overlayLayers: any = {
    'Particulate matter (PM10)': Object.assign(
        L.tileLayer.wms(config.ostluftWmsUrl, {
            layers: 'PM10_actual',
            format: 'image/png',
            transparent: true,
            version: '1.1.1',
            opacity: 0.8,
            zIndex: 10,
            attribution: '&copy; <a href="https://www.ostluft.ch/messwerte/aktuelle-belastungskarte" target="_blank">OST Luft</a>',
            pane: 'clippedOverlayPane'
        }),
        { 
            legendUrl: 'assets/images/legend_pm10.svg',
            legendDescription: 'Pollution map (modeled), 24-hour mean. Preliminary data, updated every half hour.'
        }
    ),

    'Nitrogen oxides (NO2)': Object.assign(
        L.tileLayer.wms(config.ostluftWmsUrl, {
            layers: 'NO2_actual',
            format: 'image/png',
            transparent: true,
            version: '1.1.1',
            opacity: 0.8,
            zIndex: 10,
            attribution: '&copy; <a href="https://www.ostluft.ch/messwerte/aktuelle-belastungskarte" target="_blank">OST Luft</a>',
            pane: 'clippedOverlayPane'
        }),
        { 
            legendUrl: 'assets/images/legend_no2.svg',
            legendDescription: 'Pollution map (modeled), 24-hour mean. Preliminary data, updated every half hour.'
        }
    ),

    'Ozone (O3)': Object.assign(
        L.tileLayer.wms(config.ostluftWmsUrl, {
            layers: 'O3_actual',
            format: 'image/png',
            transparent: true,
            version: '1.1.1',
            opacity: 0.8,
            zIndex: 10,
            attribution: '&copy; <a href="https://www.ostluft.ch/messwerte/aktuelle-belastungskarte" target="_blank">OST Luft</a>',
            pane: 'clippedOverlayPane'
        }),
        { 
            legendUrl: 'assets/images/legend_o3.svg',
            legendDescription: 'Pollution map (modeled), hourly average. Preliminary data, updated every half hour.'
        }
    ),

    'KBI': Object.assign(
        L.tileLayer.wms(config.ostluftWmsUrl, {
            layers: 'KBI_actual',
            format: 'image/png',
            transparent: true,
            version: '1.1.1',
            opacity: 0.8,
            zIndex: 10,
            attribution: '&copy; <a href="https://www.ostluft.ch/messwerte/aktuelle-belastungskarte" target="_blank">OST Luft</a>',
            pane: 'clippedOverlayPane'
        }),
        { legendUrl: 'assets/images/legend_kbi.svg' }
    ),

    'None': L.layerGroup(),
};
