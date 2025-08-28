import * as L from 'leaflet';
import { BaseComponent } from '../base/base.component';
import { MapComponent } from './map.component';

// Extend the Leaflet Control to create a SidebarButton
export class SidebarButton extends L.Control {
  baseComponent: BaseComponent;
  mapComponent: MapComponent;

  constructor(baseComponent: BaseComponent, mapComponent: MapComponent, options?: L.ControlOptions) {
    super(options);
    this.baseComponent = baseComponent;
    this.mapComponent = mapComponent;
  }

  override onAdd(map: L.Map): HTMLElement {
    const container = L.DomUtil.create('div', 'leaflet-control-zoom leaflet-bar leaflet-control');
    container.innerHTML = this.generateButtonHTML();
    L.DomEvent.on(container, 'click', (e) => {
      L.DomEvent.stopPropagation(e);
      this.toggleSidebar();
      container.innerHTML = this.generateButtonHTML(); // Update the button's HTML to reflect the new state
    });

    // Subscribe to the requestCloseSidebar event from the controls component
    // The controls component is now a child of the map component
    if (this.mapComponent && this.mapComponent.controls) {
      this.mapComponent.controls.requestCloseSidebar.subscribe(() => {
        // Update the button icon when sidebar is closed via the 'x' button
        container.innerHTML = this.generateButtonHTML();
      });
    }

    return container;
  }

  toggleSidebar(): void {
    if (this.baseComponent.sidebarOpen) {
      this.mapComponent.closeLeftSidebar();
    } else {
      this.mapComponent.openLeftSidebar();
    }
    // Map view will not change since sidebar overlays instead of resizing
  }

  generateButtonHTML(): string {
    const iconClass = this.baseComponent.sidebarOpen ? 'fa-solid fa-chevron-left' : 'fa-solid fa-chevron-right';
    const title = this.baseComponent.sidebarOpen ? "Close sidebar" : "Open sidebar";
    
    return `<a class="leaflet-control-zoom-in" title="${title}" role="button" aria-label="${title}" aria-disabled="false">
              <i class="toggle-sidebar-mode ${iconClass}" style="color: black;"></i>
            </a>`;
  }

  public updateButtonIcon(): void {
    const buttonContainer = document.querySelector('.leaflet-control-zoom.leaflet-bar.leaflet-control a[title*="sidebar"]')?.parentElement;
    if (buttonContainer) {
      buttonContainer.innerHTML = this.generateButtonHTML();
    }
  }
}