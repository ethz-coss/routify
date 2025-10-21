import { AfterViewInit, ChangeDetectorRef, Component, Input, ViewChild, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { SafePipe } from 'src/safe.pipe';
import { ControlsComponent } from '../controls/controls.component';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';

import { avgPm10, getProperties } from 'src/custom-route.model';

// import leaflet
import * as L from 'leaflet';
import { baseLayers, overlayLayers } from './map.layers';
import { config } from '../config';
import { getIcon, icon_a, icon_b } from './map.icons';
import { SelectAutocompleteComponent } from '../select-autocomplete/select-autocomplete.component';
import { AutoCompleteService, Feature } from 'src/autocomplete.service';
import { BackendService } from 'src/backend.service';
import { CustomEdge } from 'src/custom-edge.model';
import { CustomRoute, avgGreenIndex, avgNoise, avgSlope, getEdgeOsmIds } from 'src/custom-route.model';
import { BaseComponent } from '../base/base.component';
import { SidebarButton } from './sidebar-button';
import { QueryModeButton } from './query-mode-button';
import { InfoButton } from './info-button';
import 'leaflet-maskcanvas';
import 'leaflet-groupedlayercontrol';
import 'leaflet-compass/dist/leaflet-compass.min.js';
import 'leaflet-rotate/dist/leaflet-rotate.js';
import { of } from 'rxjs';

const osmColor: string = '#ff6200'

@Component({
  selector: 'app-map',
  standalone: true,
  imports: [
    CommonModule,
    SafePipe,
    ControlsComponent,
    MatIconModule,
    MatButtonModule
  ],
  templateUrl: './map.component.html',
  styleUrl: './map.component.css'
})
export class MapComponent implements AfterViewInit {
  @Input({ required: true }) baseComponent!: BaseComponent;
  @ViewChild('controls') controls!: ControlsComponent;

  
  ngAfterViewInit() {
    this.initMap();
    
    // Remove the problematic control container appending code since map-canvas was removed
    // The controls should work fine without this manual appending
  }

  constructor(private autocomplete: AutoCompleteService, public backend: BackendService, public cdr: ChangeDetectorRef) { }

  public config = config;
  
  public map!: L.Map;
  public querymode: boolean = false;
  public projectInfoVisible: boolean = false;
  public selectedEdge: CustomEdge | null = null;
  public mobileControlsOpen: boolean = false;

  private routes: Map<CustomRoute, L.LayerGroup<any>> = new Map();
  private indicator: L.Marker | null = null;
  private markerFrom: L.Marker | null = null;
  private markerTo: L.Marker | null = null;
  private dragStartPosition: L.LatLng | null = null;

  public queriedFeatures: L.FeatureGroup = new L.FeatureGroup();
  public queryModeHandler?: (e: L.LeafletMouseEvent) => Promise<void>;

  public boundaryFeatures: L.FeatureGroup = new L.FeatureGroup();
  public boundaryCoords: L.LatLngExpression[] | null = null;

  private legendControl: L.Control | null = null;
  public maskLayer: L.TileLayer | null = null;
  private queryModeButton: QueryModeButton | null = null;
  private infoButton: InfoButton | null = null;
  private sidebarButton: SidebarButton | null = null;

  // Mobile detection utility method
  public isMobile(): boolean {
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) || 
           window.innerWidth <= 768;
  }

  // Mobile controls methods
  public toggleMobileControls(): void {
    this.mobileControlsOpen = !this.mobileControlsOpen;
    
    // Force change detection
    this.cdr.detectChanges();
    
    // Scroll to top when opening controls
    if (this.mobileControlsOpen) {
      setTimeout(() => {
        const mobileControlsContent = document.querySelector('.mobile-controls-content') as HTMLElement;
        if (mobileControlsContent) {
          mobileControlsContent.scrollTop = 0;
        }
      }, 100); // Small delay to ensure DOM is updated
    }
    
    // Invalidate map size when controls open/close to ensure proper tile loading
    if (this.map) {
      setTimeout(() => {
        this.map.invalidateSize();
      }, 350); // Delay to account for CSS transition
    }
  }

  // Method to rotate the map programmatically
  public rotateMap(degrees: number): void {
    if (this.map && (this.map as any).setBearing) {
      (this.map as any).setBearing(degrees);
    }
  }

  // Sidebar methods
  public openSidebar(edge: CustomEdge): void {
    this.selectedEdge = edge;
    // Preserve map view when sidebar opens
    this.preserveMapView();
  }

  // Method to handle left sidebar close with view preservation
  public closeLeftSidebar(): void {
    // Delegate to base component which preserves the pixel focal point
    this.baseComponent.closeSidebar();
    
    // Update sidebar button icon when sidebar is closed via 'x' button (desktop only)
    if (this.sidebarButton) {
      this.sidebarButton.updateButtonIcon();
    }
  }

  // Method to handle left sidebar open with view preservation
  public openLeftSidebar(): void {
    // Delegate to base component which preserves the pixel focal point
    this.baseComponent.openSidebar();
    
    // Update sidebar button icon when sidebar is opened via button click (desktop only)
    if (this.sidebarButton) {
      this.sidebarButton.updateButtonIcon();
    }
  }

  // Method to preserve map view during sidebar transitions
  private preserveMapView(): void {
    const currentCenter = this.map.getCenter();
    const currentZoom = this.map.getZoom();
    
    // Store the current view state
    const currentBounds = this.map.getBounds();
    
    // Use a different approach that doesn't disable map dragging
    // Just set the view without disabling interactions
    this.map.setView(currentCenter, currentZoom, { animate: false, noMoveStart: true });
    
    // Use requestAnimationFrame to ensure DOM has updated
    requestAnimationFrame(() => {
      // Force the map to maintain its current view
      this.map.setView(currentCenter, currentZoom, { animate: false, noMoveStart: true });
    });
  }

  public deactivateQueryMode(): void {
    // Preserve map view before closing
    const currentCenter = this.map.getCenter();
    const currentZoom = this.map.getZoom();
    
    this.querymode = false;
    this.selectedEdge = null;
    
    // Reset any highlighted polylines
    this.queriedFeatures.eachLayer((layer: any) => {
      if (layer.setStyle) {
        layer.setStyle({ color: '#ff6200', opacity: 0.7 });
      }
    });
    
    // Remove queried features from map
    this.queriedFeatures.removeFrom(this.map);
    this.queriedFeatures = new L.FeatureGroup();
    
    // Update cursor
    document.querySelectorAll('.leaflet-interactive').forEach(element => { 
      (element as any).style.cursor = "pointer"; 
    });
    
    this.cdr.detectChanges();
    
    // Preserve map view when sidebar closes
    this.preserveMapView();
    
    // Update the query mode button icon
    if (this.queryModeButton) {
        this.queryModeButton.updateButtonIcon();
    }
    
    this.cdr.detectChanges();
  }

  public openProjectInfo(): void {
    this.projectInfoVisible = true;
    this.cdr.detectChanges();
  }

  public closeProjectInfo(): void {
    this.projectInfoVisible = false;
    this.cdr.detectChanges();
  }

  public getOsmFrameUrl(): string {
    if (!this.selectedEdge) return '';
    
    // Calculate the center point between source and target
    const centerLat = (this.selectedEdge.source.lat + this.selectedEdge.target.lat) / 2;
    const centerLng = (this.selectedEdge.source.lon + this.selectedEdge.target.lon) / 2;
    
    // Use OSM export embed API which is designed for iframe embedding
    // Calculate a bounding box that ensures the way is visible
    const latDiff = Math.abs(this.selectedEdge.source.lat - this.selectedEdge.target.lat);
    const lngDiff = Math.abs(this.selectedEdge.source.lon - this.selectedEdge.target.lon);
    
    // Use a minimum bounding box size to ensure visibility
    const minSize = 0.002; // Larger minimum size for better visibility
    const latSize = Math.max(latDiff * 3, minSize); // 3x the way size for context
    const lngSize = Math.max(lngDiff * 3, minSize);
    
    const bbox = `${centerLng - lngSize/2},${centerLat - latSize/2},${centerLng + lngSize/2},${centerLat + latSize/2}`;
    
    // Use OSM export embed with way highlighting and marker
    return `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&way=${this.selectedEdge.osmId}&marker=${centerLat},${centerLng}`;
  }

  public openOsmWay(): void {
    if (this.selectedEdge) {
      const osmUrl = `https://www.openstreetmap.org/way/${this.selectedEdge.osmId}`;
      window.open(osmUrl, '_blank');
    }
  }

  public showDataPoint(from: L.LatLng, to: L.LatLng): void {
    if (this.controls) {
      this.controls.showDataPoint(from, to);
    }
  }

  // Public method for travel time formatting
  public formatTravelTime(timeValue: number): string {
    if (timeValue < 1) {
      const seconds = timeValue * 60;
      return `${seconds.toFixed(1)}s`;
    } else {
      // If 1 minute or more, display in minutes
      return `${timeValue.toFixed(1)}min`;
    }
  }

  // Add touch rotation support for mobile devices
  private addTouchRotationSupport(): void {
    // Only add touch rotation support on mobile devices
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) || 
                     window.innerWidth <= 768;
    
    if (!isMobile) {
      return;
    }

    let startAngle = 0;
    let currentBearing = 0;
    let isRotating = false;

    const mapContainer = this.map.getContainer();

    // Handle touch start
    const handleTouchStart = (e: TouchEvent) => {
      if (e.touches.length === 2) {
        e.preventDefault();
        isRotating = true;
        
        // Calculate initial angle between two touch points
        const touch1 = e.touches[0];
        const touch2 = e.touches[1];
        startAngle = Math.atan2(touch2.clientY - touch1.clientY, touch2.clientX - touch1.clientX) * 180 / Math.PI;
        
        // Get current bearing
        currentBearing = (this.map as any).getBearing ? (this.map as any).getBearing() : 0;
      }
    };

    // Handle touch move
    const handleTouchMove = (e: TouchEvent) => {
      if (e.touches.length === 2 && isRotating) {
        e.preventDefault();
        
        // Calculate current angle between two touch points
        const touch1 = e.touches[0];
        const touch2 = e.touches[1];
        const currentAngle = Math.atan2(touch2.clientY - touch1.clientY, touch2.clientX - touch1.clientX) * 180 / Math.PI;
        
        // Calculate rotation delta
        const deltaAngle = currentAngle - startAngle;
        
        // Apply rotation
        const newBearing = (currentBearing + deltaAngle) % 360;
        if ((this.map as any).setBearing) {
          (this.map as any).setBearing(newBearing);
        }
      }
    };

    // Handle touch end
    const handleTouchEnd = (e: TouchEvent) => {
      if (isRotating) {
        isRotating = false;
      }
    };

    // Add event listeners only for mobile
        mapContainer.addEventListener('touchstart', handleTouchStart, { passive: false });
    mapContainer.addEventListener('touchmove', handleTouchMove, { passive: false });
    mapContainer.addEventListener('touchend', handleTouchEnd, { passive: false });
  }

  private async initMap(): Promise<void> {
    // Check if device is mobile
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) || 
                     window.innerWidth <= 768;
    
    // define map object with rotation enabled
    this.map = L.map('map', {
      layers: [baseLayers['OpenStreetMap']],
      center: new L.LatLng(47.38103985765332, 8.53961786523515),
      zoom: 5,
      ...({ 
        rotate: true, 
        rotateControl: true,
        // Enable touch rotation on mobile
        touchRotate: isMobile,
        touchRotateThreshold: 10
      } as any)  // Enable rotation with type assertion
    });

    // request and setup boundary
    await this.loadBoundary();

    // Create a custom pane for the overlay
    this.map.createPane('clippedOverlayPane');
    // Make sure the pane sits above the base tile layer
    this.map.getPane('clippedOverlayPane')!.style.zIndex = '650';

    // add boundary
    this.boundaryFeatures.addTo(this.map);

    // add queryMode button
    if (!this.isMobile()) {
      this.queryModeButton = new QueryModeButton(this, { position: 'topleft' });
      this.queryModeButton.addTo(this.map);
    }

    // add info button
    this.infoButton = new InfoButton(this, { position: 'topleft' });
    this.infoButton.addTo(this.map);

    // add click event handler for querymode (only on desktop)
    if (this.queryModeButton) {
      this.queryModeHandler = this.queryModeButton.handleQueryEvent.bind(this.queryModeButton);
      this.map.on('click', this.queryModeHandler);
    }

    // add sidebar button (only on desktop)
    if (!this.isMobile()) {
      this.sidebarButton = new SidebarButton(this.baseComponent, this, { position: 'topleft' });
      this.sidebarButton.addTo(this.map);
    }

    this.map.invalidateSize()
    this.map.setView(new L.LatLng(47.38103985765332, 8.53961786523515), 13)
    L.control.scale().addTo(this.map)
    
    // Add custom compass control
    try {
      
      // Create a custom compass control that works with rotation (desktop only)
      const compassControl = L.Control.extend({
        options: {
          position: 'topright'
        },
        onAdd: function(map: L.Map) {
          // Don't add compass on mobile
          const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) || 
                           window.innerWidth <= 768;
          if (isMobile) {
            return L.DomUtil.create('div'); // Return empty container
          }
          const container = L.DomUtil.create('div', 'leaflet-control-compass');
          
          // Function to update compass display
          const updateCompass = () => {
            const bearing = (map as any).getBearing ? (map as any).getBearing() : 0;
            const direction = bearing === 0 ? 'N' : bearing === 90 ? 'E' : bearing === 180 ? 'S' : bearing === 270 ? 'W' : `${Math.round(bearing)}°`;
            
            container.innerHTML = `
              <div style="
                background: white;
                border: 2px solid rgba(0,0,0,0.2);
                border-radius: 4px;
                padding: 5px;
                cursor: pointer;
                font-weight: bold;
                text-align: center;
                min-width: 40px;
                box-shadow: 0 1px 5px rgba(0,0,0,0.4);
                user-select: none;
              ">
                <div style="font-size: 16px;">🧭</div>
                <div style="font-size: 10px;">${direction}</div>
              </div>
            `;
          };
          
          // Initial update
          updateCompass();
          
          // Update on map rotation
          if (map.on) {
            map.on('rotate', updateCompass);
          }
          
          // Add click handler to rotate the map
          container.onclick = function() {
            const currentBearing = (map as any).getBearing ? (map as any).getBearing() : 0;
            // Rotate the map by 90 degrees clockwise on each click
            const newBearing = (currentBearing + 90) % 360;
            if ((map as any).setBearing) {
              (map as any).setBearing(newBearing);
            }
          };
          
          // Add right-click handler to reset rotation
          container.oncontextmenu = function(e) {
            e.preventDefault();
            if ((map as any).setBearing) {
              (map as any).setBearing(0);
            }
          };
          
          return container;
        }
      });
      
      // Add enhanced rotation controls (desktop only)
      const rotationControl = L.Control.extend({
        options: {
          position: 'topright'
        },
        onAdd: function(map: L.Map) {
          // Don't add rotation controls on mobile
          const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) || 
                           window.innerWidth <= 768;
          if (isMobile) {
            return L.DomUtil.create('div'); // Return empty container
          }
          const container = L.DomUtil.create('div', 'leaflet-control-rotation');
          container.style.cssText = `
            background: white;
            border: 2px solid rgba(0,0,0,0.2);
            border-radius: 4px;
            padding: 5px;
            margin-top: 5px;
            box-shadow: 0 1px 5px rgba(0,0,0,0.4);
            user-select: none;
          `;
          
          container.innerHTML = `
            <div style="text-align: center; font-size: 12px; font-weight: bold; margin-bottom: 5px;">Rotation</div>
            <div style="display: flex; gap: 2px; justify-content: center;">
              <button style="
                width: 25px; height: 25px; 
                border: 1px solid #ccc; 
                background: #f0f0f0; 
                cursor: pointer; 
                font-size: 10px;
                border-radius: 2px;
              " title="Rotate 45° CCW">↶</button>
              <button style="
                width: 25px; height: 25px; 
                border: 1px solid #ccc; 
                background: #f0f0f0; 
                cursor: pointer; 
                font-size: 10px;
                border-radius: 2px;
              " title="Rotate 90° CCW">⟲</button>
              <button style="
                width: 25px; height: 25px; 
                border: 1px solid #ccc; 
                background: #f0f0f0; 
                cursor: pointer; 
                font-size: 10px;
                border-radius: 2px;
              " title="Reset to North">N</button>
              <button style="
                width: 25px; height: 25px; 
                border: 1px solid #ccc; 
                background: #f0f0f0; 
                cursor: pointer; 
                font-size: 10px;
                border-radius: 2px;
              " title="Rotate 90° CW">⟳</button>
              <button style="
                width: 25px; height: 25px; 
                border: 1px solid #ccc; 
                background: #f0f0f0; 
                cursor: pointer; 
                font-size: 10px;
                border-radius: 2px;
              " title="Rotate 45° CW">↷</button>
            </div>
          `;
          
          const buttons = container.querySelectorAll('button');
          
          // Add event listeners for rotation buttons
          buttons[0].onclick = () => { // 45° CCW
            const currentBearing = (map as any).getBearing ? (map as any).getBearing() : 0;
            const newBearing = (currentBearing - 45 + 360) % 360;
            if ((map as any).setBearing) {
              (map as any).setBearing(newBearing);
            }
          };
          
          buttons[1].onclick = () => { // 90° CCW
            const currentBearing = (map as any).getBearing ? (map as any).getBearing() : 0;
            const newBearing = (currentBearing - 90 + 360) % 360;
            if ((map as any).setBearing) {
              (map as any).setBearing(newBearing);
            }
          };
          
          buttons[2].onclick = () => { // Reset to North
            if ((map as any).setBearing) {
              (map as any).setBearing(0);
            }
          };
          
          buttons[3].onclick = () => { // 90° CW
            const currentBearing = (map as any).getBearing ? (map as any).getBearing() : 0;
            const newBearing = (currentBearing + 90) % 360;
            if ((map as any).setBearing) {
              (map as any).setBearing(newBearing);
            }
          };
          
          buttons[4].onclick = () => { // 45° CW
            const currentBearing = (map as any).getBearing ? (map as any).getBearing() : 0;
            const newBearing = (currentBearing + 45) % 360;
            if ((map as any).setBearing) {
              (map as any).setBearing(newBearing);
            }
          };
          
          return container;
        }
      });
      
      new rotationControl().addTo(this.map);
      
      new compassControl().addTo(this.map);
    } catch (error) {
      // swallow compass control errors silently in production
    }

    // prevent leaflet from loading air quality tiles outside the bounds
    Object.values(overlayLayers).forEach(layer => {
      (layer as any).options.bounds = L.latLngBounds(this.boundaryCoords!);
    });

    // Grouped overlays: group your overlay layers into categories.
    const groupedOverlays = {
      'Air Quality': overlayLayers
    };

    // Create the grouped layers control.
    // The plugin adds the method L.control.groupedLayers.
    const groupedLayersControl = (L.control as any).groupedLayers(baseLayers, groupedOverlays, {
      collapsed: true,  // Set to true to collapse groups by default
      exclusiveGroups: ["Air Quality"],
      groupCheckboxes: true
    });

    groupedLayersControl.addTo(this.map);

    this.map.on('overlayadd', (event: any) => {
      this.removeLegend();
      this.addLegend(event.layer);  // Show the corresponding legend
    });
    
    // this.map.on('overlayremove', () => {
    //   this.removeLegend();  // Remove legend when overlay is turned off
    // });

    this.map.whenReady(() => {
      this.applyClipPath();
      setTimeout(() => {
        this.map.invalidateSize();
        this.map.setZoom(this.map.getZoom());
      }, 500);
      
      // Add touch rotation support for mobile
      this.addTouchRotationSupport();
    });
  
    // Update the clip path on zoom or move events
    this.map.on('zoom move', () => {
      this.applyClipPath();
    });

    this.map.eachLayer((layer: L.Layer) => {
      // Check if the layer is an instance of L.TileLayer and is added to the map
      if (layer instanceof L.TileLayer && this.map.hasLayer(layer)) {
        layer.redraw();
      }
    });
  }

  private applyClipPath() {
    const pane = this.map.getPane('clippedOverlayPane') as HTMLElement;
    if (!pane) return;
  
    // Convert each latLng coordinate to a layer point (in pixels)
    const points = this.boundaryCoords!.map(latlng => {
      const layerPoint = this.map.latLngToLayerPoint(L.latLng(latlng));
      return `${layerPoint.x}px ${layerPoint.y}px`;
    });
    // Create the CSS polygon string
    const clipPathValue = `polygon(${points.join(',')})`;
    pane.style.clipPath = clipPathValue;
    (pane.style as any).webkitClipPath = clipPathValue; // for Safari compatibility
  }

  async loadBoundary() {
    try {
      const response: any = await this.backend.requestBoundary();
  
      if (response && response.features[0]) {
        let geojsonFeature = response.features[0];
  
        // Coordinates of your GeoJSON polygon
        const polygonCoords: L.LatLngExpression[] = L.GeoJSON.coordsToLatLngs(
          geojsonFeature.geometry.coordinates[0]
        );
  
        // Large rectangle covering the whole visible area
        const outerBounds: L.LatLngExpression[] = [[-90, -360], [-90, 360], [90, 360], [90, -360]];
  
        // Create a cut-out effect using the polygon coordinates
        const greyLayerCoords: L.LatLngExpression[][] = [outerBounds, polygonCoords];

        this.boundaryCoords = polygonCoords;
  
        // Add a grey overlay with a hole
        const greyLayer = L.polygon(greyLayerCoords, {
          color: '#000',
          weight: 0.0,
          fillColor: '#999',
          fillOpacity: 0.5,
        }).addTo(this.boundaryFeatures);
  
        // Ensure the boundary polygon is visible
        const polygon = L.polygon(polygonCoords, {
          color: '#999',
          weight: 0.5,
          fillOpacity: 0.0,
        }).addTo(this.boundaryFeatures);
  
        // Boundary successfully loaded
      } else {
        console.error("UNABLE_TO_REQUEST_BOUNDARY");
      }
    } catch (error) {
      console.error("Error requesting boundary:", error);
    }
  }
  

  public resize(): void {
    setTimeout(() => {
      this.map.invalidateSize();
      this.cdr.detectChanges();
    }, 100);
  }

  public clear(): void {
    for (let [key, value] of this.routes) {
      value.remove();
    }
    this.indicator?.remove();
    this.markerFrom?.remove();
    this.markerTo?.remove();
    this.indicator = null;
  }

  public indicatePosition(latlngs: L.LatLng) {
    if (this.indicator) {
      this.indicator.remove();
      this.indicator = L.marker(latlngs, { icon: getIcon(this.controls.transportMode) }).addTo(this.map);
    } else {
      this.indicator = L.marker(latlngs, { icon: getIcon(this.controls.transportMode) }).addTo(this.map);
    }
  }

  private getSegment(route: CustomRoute, edge: CustomEdge) {

    let latlngs: L.LatLng[] = [];
    // set coordinates from
    latlngs.push(L.latLng(edge.source.lat, edge.source.lon));
    // set coordinates to
    latlngs.push(L.latLng(edge.target.lat, edge.target.lon));

    return L.polyline(latlngs, {
      "color": getProperties(route.routingMode).lineColor,
      "weight": 5,
      "opacity": 0.7
    }).on('mouseover', (e) => {
      e.target.setStyle({
        weight: 7,
        opacity: 1
      });
      let co: Array<L.LatLng> = e.sourceTarget._latlngs;
      this.showDataPoint(co[0], co[1]);
    }).on('mouseout', (e) => {
      e.target.setStyle({
        weight: 6,
        opacity: 0.7
      });
      // not clean version of popup content (probably better implementation possible using Angular SafeHtml and Sanatizer)
    }).bindPopup(`
      <style>
        .custom-star { color: grey; }
        .custom-active-star { color: yellow; -webkit-text-stroke-width: 1px; -webkit-text-stroke-color: black; }
        .submit-rating { color: green; }
        .remove-rating { color: red; display: hidden; }
      </style>
      <span><b>average values of route</b></span><hr>
      <table>
        <tr><th>routing mode:</th><td>${route.routingMode}</td></tr>
        <tr><th>green index:</th><td>${avgGreenIndex(route).toFixed(2)}</td></tr>
        <tr><th>elevation:</th><td>${(avgSlope(route) * 100).toFixed(2)} %</td></tr>
        <tr><th>air quality:</th><td>${avgPm10(route).toFixed(2)} PM10 [µg/m³]</td></tr>
        <tr><th>noise:</th><td>${avgNoise(route).toFixed(2)} db</td></tr>
      </table>
    `).on('popupopen', (e) => {
      if (this.querymode) this.map.closePopup();
    }).on('click', (e) => {
      if (this.querymode && this.queryModeHandler) {
        this.queryModeHandler(e);
      }
    });
  }

  

  public removeRoute(route: CustomRoute) {
    if (this.routes.has(route)) {
      this.routes.get(route)?.remove();
      this.routes.delete(route);
    }
  }

  public addRoute(route: CustomRoute) {
    let routeFeature = new L.FeatureGroup();

    // add start edge, connectiong start to street network
    let startEdge = this.getSegment(route, route.edges[0]);
    startEdge.addTo(routeFeature);

    // add end edge, connectiong destination with street network
    let endEdge = this.getSegment(route, route.edges[route.edges.length - 1]);
    endEdge.addTo(this.map);


    route.edges.forEach((edge: CustomEdge) => {
      let segment = this.getSegment(route, edge);
      segment.addTo(routeFeature);
    });

    this.routes.set(route, routeFeature);
    routeFeature.addTo(this.map);

    let havezoom = true;
    if (this.markerFrom) {
      this.markerFrom.remove();
      havezoom = false;
    }
    if (this.markerTo) {
      this.markerTo.remove();
    }

    // Prefer exact user-selected coordinates (from autocomplete inputs) over snapped route vertices
    let start: L.LatLng;
    let end: L.LatLng;

    if (this.controls?.input_from?.value && this.controls.input_from.value.latitude && this.controls.input_from.value.longitude) {
      start = L.latLng(this.controls.input_from.value.latitude, this.controls.input_from.value.longitude);
    } else {
      start = L.latLng(route.startVertex.lat, route.startVertex.lon);
    }

    if (this.controls?.input_to?.value && this.controls.input_to.value.latitude && this.controls.input_to.value.longitude) {
      end = L.latLng(this.controls.input_to.value.latitude, this.controls.input_to.value.longitude);
    } else {
      end = L.latLng(route.endVertex.lat, route.endVertex.lon);
    }

    // set start (A) and end (B) marker
    this.markerFrom = L.marker(start, { 
      icon: icon_a, 
      draggable: true,
      interactive: true,
      autoPan: false
    })
      .on('click', (event) => {
        alert('Start marker clicked!');
      })
      .on('dragstart', (event) => {
        // Store the initial position when drag starts
        this.dragStartPosition = (event.target as L.Marker).getLatLng();
      })
      .on('drag', (event) => {
        // Dragging
      })
      .on('dragend', (event) => {
        if (this.controls?.input_from) {
          this.onDrag(event, this.controls.input_from);
        } else {
          console.error('input_from not available');
        }
      })
      .addTo(this.map);
      
    this.markerTo = L.marker(end, { 
      icon: icon_b, 
      draggable: true,
      interactive: true,
      autoPan: false
    })
      .on('click', (event) => {
        alert('End marker clicked!');
      })
      .on('dragstart', (event) => {
        // Store the initial position when drag starts
        this.dragStartPosition = (event.target as L.Marker).getLatLng();
      })
      .on('drag', (event) => {
        // Dragging
      })
      .on('dragend', (event) => {
        if (this.controls?.input_to) {
          this.onDrag(event, this.controls.input_to);
        } else {
          console.error('input_to not available');
        }
      })
      .addTo(this.map);
      
    // Add a delay to ensure controls are properly initialized
    setTimeout(() => {
      if (this.controls?.input_from && this.controls?.input_to) {
        // Controls are now available for drag events
      } else {
        // Controls not yet available, will retry on drag
        // Retry after another delay
        setTimeout(() => {
          if (this.controls?.input_from && this.controls?.input_to) {
            // Controls are now available after retry
          } else {
            console.error('Controls still not available after retry');
          }
        }, 2000);
      }
    }, 2000);
  }
  
  public zoomOut() {
    // setTimeout(() => {
    //   this.map.zoomOut(2);
    // }, 1000);
  }

  public async onDrag(event: L.DragEndEvent, input: SelectAutocompleteComponent): Promise<void> {
    if (!input) {
      console.error('Input component is null or undefined');
      return;
    }
    
    var marker = event.target as L.Marker;
    
    // Get the exact coordinates from the drag end event
    const newLatLng = marker.getLatLng();
    let markerType = '';
    
    // Determine which marker was moved
    if (marker === this.markerFrom) {
      markerType = 'Start (A)';
    } else if (marker === this.markerTo) {
      markerType = 'End (B)';
    }
    
    
    try {
      // Create a feature with the exact new coordinates
      let address: Feature = {
        id: 0,
        latitude: newLatLng.lat,
        longitude: newLatLng.lng,
        osm_id: -1,
        country: '',
        city: '',
        countrycode: '',
        postcode: '',
        locality: '',
        county: '',
        type: '',
        osm_type: '',
        osm_key: '',
        housenumber: '',
        street: '',
        district: '',
        osm_value: '',
        name: '',
        state: '',
        displayname: `${newLatLng.lat.toFixed(6)}, ${newLatLng.lng.toFixed(6)}`
      };
      
      // Update the input field with the new coordinates
      input.setValue(address);
      input.updateField();
      this.cdr.detectChanges();
      
      // Also directly update the controls component's input field reference
      if (this.controls) {
        if (marker === this.markerFrom) {
          this.controls.input_from = input;
        } else if (marker === this.markerTo) {
          this.controls.input_to = input;
        }
      }
      
      // Wait for the input field to be fully updated before recalculating route
      setTimeout(() => {
        if (this.controls) {
          this.controls.forceRouteRecalculation();
        } else {
          console.error('Controls component not available');
        }
      }, 1000); // Increased delay to ensure input is fully updated
    } catch (error) {
      console.error('Error updating address after drag:', error);
    }
  }

  public async onMove(event: L.LeafletEvent, input: SelectAutocompleteComponent): Promise<void> {
    var marker = event.target as L.Marker;
    
    // Get the new position (after move)
    const newLatLng = marker.getLatLng();
    
    // Determine which marker was moved and get the old position
    let oldLatLng: L.LatLng | null = null;
    let markerType = '';
    
    if (marker === this.markerFrom) {
      oldLatLng = this.markerFrom.getLatLng();
      markerType = 'Start (A)';
    } else if (marker === this.markerTo) {
      oldLatLng = this.markerTo.getLatLng();
      markerType = 'End (B)';
    }
    
    // Alert old and new positions
    if (oldLatLng) {
      alert(`${markerType} marker repositioned!\n\nOld position: ${oldLatLng.lat.toFixed(6)}, ${oldLatLng.lng.toFixed(6)}\nNew position: ${newLatLng.lat.toFixed(6)}, ${newLatLng.lng.toFixed(6)}`);
    } else {
      alert(`${markerType} marker repositioned!\n\nNew position: ${newLatLng.lat.toFixed(6)}, ${newLatLng.lng.toFixed(6)}`);
    }
    
    let address: Feature = await this.autocomplete.requestAddress(newLatLng);
    
    // Properly update the input field with the new address
    input.setValue(address);
    input.updateField();
    
    // Force change detection
    this.cdr.detectChanges();
    
    // Add a longer delay to ensure everything is updated
    setTimeout(() => {
      // Force route recalculation using the new method
      this.controls.forceRouteRecalculation();
    }, 500); // Increased delay to ensure input is updated
  }

  private addLegend(layer: any): void {
    if (layer.legendUrl) {
      if (!this.legendControl) {
        this.legendControl = new (L.Control.extend({
          onAdd: function() {
            let div = L.DomUtil.create('div', 'legend leaflet-control-legend');
            let legendContent = `<img src="${layer.legendUrl}" alt="Legend" style="width: 150px;">`;
            
            // Add tooltip if description exists
            if (layer.legendDescription) {
              div.title = layer.legendDescription;
            }
            
            div.innerHTML = legendContent;
            return div;
          }
        }))({ position: 'bottomright' });
      } else {
        // Update the legend image if it already exists
        const legendDiv = document.querySelector('.legend img');
        if (legendDiv) {
          (legendDiv as HTMLImageElement).src = layer.legendUrl;
        }
        
        // Update tooltip
        const legendContainer = document.querySelector('.legend') as HTMLElement;
        if (legendContainer) {
            if (layer.legendDescription) {
                legendContainer.title = layer.legendDescription;
            } else {
                legendContainer.title = '';
            }
        }
      }
      this.legendControl.addTo(this.map);
    }
  }
  
  private removeLegend(): void {
    if (this.legendControl) {
      this.map.removeControl(this.legendControl);
      this.legendControl = null;
    }
  }
}
