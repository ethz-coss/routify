import * as L from 'leaflet';
import { BaseComponent } from '../base/base.component';
import { MapComponent } from './map.component';
import { CustomEdge } from 'src/custom-edge.model';

const osmColor: string = '#ff6200'

// Extend the Leaflet Control to create a QueryModeButton
export class QueryModeButton extends L.Control {
    private mapComponent: MapComponent;
    private activePolyline: L.Polyline | null = null;
    private addedEdgeIds: Set<number> = new Set(); // Track added edge IDs to prevent duplicates

    constructor(mapComponent: MapComponent, options?: L.ControlOptions) {
        super(options);
        this.mapComponent = mapComponent;
    }

    override onAdd(map: L.Map): HTMLElement {
        const container = L.DomUtil.create('div', 'leaflet-control-zoom leaflet-bar leaflet-control');
        container.innerHTML = this.generateButtonHTML();
        L.DomEvent.on(container, 'click', (e) => {
            L.DomEvent.stopPropagation(e);
            e.preventDefault();
            this.callbackQuery(e);
            container.innerHTML = this.generateButtonHTML(); // Update the button's HTML to reflect the new state
        });
        return container;
    }

    public callbackQuery(e: any): void {
        this.mapComponent.querymode = !this.mapComponent.querymode;
        document.querySelectorAll('.leaflet-mouse-marker').forEach(element => { element });
        document.querySelectorAll('.leaflet-interactive').forEach(element => { (element as any).style.cursor = (this.mapComponent.querymode) ? "help" : "pointer" });
        this.mapComponent.cdr.detectChanges();
        if(this.mapComponent.querymode) {
            this.mapComponent.queriedFeatures.addTo(this.mapComponent.map);
            this.mapComponent.selectedEdge = null; // Clear any previously selected edge
            // Preserve map view when query mode is activated
            const currentCenter = this.mapComponent.map.getCenter();
            const currentZoom = this.mapComponent.map.getZoom();
            requestAnimationFrame(() => {
                this.mapComponent.map.invalidateSize();
                this.mapComponent.map.setView(currentCenter, currentZoom, { animate: false, noMoveStart: true });
            });
        } else {
            this.mapComponent.queriedFeatures.removeFrom(this.mapComponent.map);
            this.mapComponent.queriedFeatures = new L.FeatureGroup;
            this.mapComponent.selectedEdge = null;
            this.addedEdgeIds.clear(); // Clear added edge IDs when query mode is deactivated
        }
    }

    public updateButtonIcon(): void {
        // Find the button container and update its HTML
        const buttonContainer = document.querySelector('.leaflet-control-zoom.leaflet-bar.leaflet-control a[title*="query-mode"]')?.parentElement;
        if (buttonContainer) {
            buttonContainer.innerHTML = this.generateButtonHTML();
        }
    }

    private generateButtonHTML(): string {
        const iconClass = this.mapComponent.querymode ? 'fa-solid fa-trash' : 'fa-brands fa-searchengin';
        return `<a class="leaflet-control-zoom-in" title="${(!this.mapComponent.querymode) ? "Activate" : "Deactivate"} query-mode" role="button" aria-label="${(!this.mapComponent.querymode) ? "Activate" : "Deactivate"} query-mode" aria-disabled="false">
                    <i class="toggle-query-mode ${iconClass}" style="${(this.mapComponent.querymode) ? osmColor : "black"}"></i>
                </a>`;
    }

    public async handleQueryEvent(e: L.LeafletMouseEvent): Promise<void> {
        if (!this.mapComponent.querymode) return;
    
        this.addQueryIndicator(e.latlng);
        const features: CustomEdge[] = await this.mapComponent.backend.queryFeatures(e.latlng) as CustomEdge[];
        
        features.forEach(feature => this.createAndAddPolyline(feature));
    }
    
    private createAndAddPolyline(feature: CustomEdge): void {
            // Check if this edge has already been added
    if (this.addedEdgeIds.has(feature.id)) {
      return;
    }
    
    // Add the edge ID to the set to prevent future duplicates
    this.addedEdgeIds.add(feature.id);
    
    const polylineOptions = {
      weight: 4,
      opacity: 0.7,
      color: osmColor
    };

    const sourceLatLng = L.latLng(feature.source.lat, feature.source.lon);
    const targetLatLng = L.latLng(feature.target.lat, feature.target.lon);

    const polyline: L.Polyline = L.polyline([sourceLatLng, targetLatLng], polylineOptions)
      .on('click', e => this.onPolylineClick(e, feature))
      .on('mouseover', e => this.onPolylineMouseOver(e))
      .on('mouseout', e => this.onPolylineMouseOut(e));

    polyline.addTo(this.mapComponent.queriedFeatures);
  }
    
    private onPolylineClick(e: L.LeafletMouseEvent, feature: CustomEdge): void {
        L.DomEvent.stopPropagation(e);
        if (!this.mapComponent.querymode) return;

        // Reset the style of the previously active polyline
        if (this.activePolyline) {
            this.activePolyline.setStyle({ color: osmColor, opacity: 0.7 });
        }

        // Set the newly clicked polyline as active
        this.activePolyline = e.target;
        e.target.setStyle({ color: "var(--primary-blue, #007bff)", opacity: 1 });
    
        // Open the sidebar instead of modal
        this.mapComponent.openSidebar(feature);
    }
    
    private onPolylineMouseOver(e: L.LeafletMouseEvent): void {
        e.target.setStyle({
            weight: 7,
            opacity: 1
        });
    }
    
    private onPolylineMouseOut(e: L.LeafletMouseEvent): void {
        e.target.setStyle({
            weight: 4, // Adjusted to match the initial weight for consistency
            opacity: 0.7
        });
    }
    
    private async addQueryIndicator(latlng: L.LatLngExpression) {
        let circle: L.Circle = L.circle(latlng, {radius: 20, color: osmColor, opacity: 1.0}).addTo(this.mapComponent.map)
        this.changeOpQueryIndeicator(circle, 1.0)
    }

    private changeOpQueryIndeicator(c: L.Circle, op: number) {
        if(op > 0.0) {
            c.setStyle({'opacity' : op})
            setTimeout(()=>{
            this.changeOpQueryIndeicator(c, (op - 0.05))
            }, 40);
        } else {
            c.remove()
        }
    }
}