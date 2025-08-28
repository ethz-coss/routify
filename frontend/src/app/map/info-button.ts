import * as L from 'leaflet';
import { BaseComponent } from '../base/base.component';
import { MapComponent } from './map.component';

// Extend the Leaflet Control to create an InfoButton
export class InfoButton extends L.Control {
    private mapComponent: MapComponent;

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
            this.callbackInfo(e);
        });
        return container;
    }

    public callbackInfo(e: any): void {
        this.mapComponent.openProjectInfo();
    }

    private generateButtonHTML(): string {
        return `<a class="leaflet-control-zoom-in" title="About Routify" role="button" aria-label="About Routify" aria-disabled="false">
                    <i class="fa-solid fa-info-circle" style="color: var(--primary-blue, #007bff);"></i>
                </a>`;
    }
}
