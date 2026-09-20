import * as L from 'leaflet';
import { MapComponent } from './map.component';

// Leaflet control that starts the guided tour (mirrors InfoButton)
export class TourButton extends L.Control {
    private mapComponent: MapComponent;

    constructor(mapComponent: MapComponent, options?: L.ControlOptions) {
        super(options);
        this.mapComponent = mapComponent;
    }

    override onAdd(map: L.Map): HTMLElement {
        const container = L.DomUtil.create('div', 'leaflet-control-zoom leaflet-bar leaflet-control');
        container.innerHTML = `<a class="leaflet-control-zoom-in" title="Guided tour" role="button" aria-label="Guided tour" aria-disabled="false">
                    <i class="fa-solid fa-graduation-cap" style="color: var(--primary-blue, #007bff);"></i>
                </a>`;
        L.DomEvent.on(container, 'click', (e) => {
            L.DomEvent.stopPropagation(e);
            e.preventDefault();
            this.mapComponent.controls?.startTour();
        });
        return container;
    }
}
