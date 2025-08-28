import { ChangeDetectorRef, Component, Input, ViewChild, ElementRef, EventEmitter, Output} from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { FormsModule } from '@angular/forms';
import { MatExpansionModule } from '@angular/material/expansion';
import { isDevMode } from '@angular/core';
// import custom components
import * as L from 'leaflet';
import { SelectAutocompleteComponent } from '../select-autocomplete/select-autocomplete.component'
import { CustomChartComponent } from "../custom-chart/custom-chart.component";
import { ParameterSliderComponent } from '../parameter-slider/parameter-slider.component';
import { MapComponent } from '../map/map.component';
import { getProperties } from 'src/custom-route.model';
import { BackendService } from 'src/backend.service';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import Swal from 'sweetalert2';
import { DataPoint, normalizeDataPoints, smoothDataPoints } from '../custom-chart/data-point.model';
import { CustomRoute, getMetaData } from 'src/custom-route.model';
import { Presets } from 'src/app/global-presets'
import { VersionService } from 'src/version.service';
import { config } from '../config';

@Component({
  selector: 'app-controls',
  standalone: true,
  templateUrl: './controls.component.html',
  styleUrl: './controls.component.css',
  imports: [
    CommonModule,
    MatButtonToggleModule,
    MatIconModule,
    FormsModule,
    MatButtonModule,
    MatExpansionModule,
    // import custom components
    SelectAutocompleteComponent,
    CustomChartComponent,
    ParameterSliderComponent
  ]
})
export class ControlsComponent {

  @Input() map: MapComponent | undefined;

  constructor(public routing: BackendService, private cdr: ChangeDetectorRef, private sanitizer: DomSanitizer, private versionService: VersionService) {
    this.versionService.getVersion().subscribe(data => {
      this.version = data;
    });
  }

  public config = config;

  @ViewChild('input_from') input_from: SelectAutocompleteComponent | undefined;
  @ViewChild('input_to') input_to: SelectAutocompleteComponent | undefined;

  @ViewChild('slider_elevation') slider_elevation: ParameterSliderComponent | undefined;
  @ViewChild('slider_green') slider_green: ParameterSliderComponent | undefined;
  @ViewChild('slider_noise') slider_noise: ParameterSliderComponent | undefined;
  @ViewChild('slider_air') slider_air: ParameterSliderComponent | undefined;
  // feedback sliders removed
  @ViewChild('context_slider') context_slider: ParameterSliderComponent | undefined;

  @ViewChild('chart_main') chart_main: CustomChartComponent | undefined;

  @Output() requestCloseSidebar = new EventEmitter<void>();

  public devMode: boolean = isDevMode() || ['localhost', '127.0.0.1', 'dev.routify.ch'].includes(window.location.hostname);
  public version: any;
  // charts collapsed by default
  public directionsVisible: boolean = false;
  public metricsVisible: boolean = false;
  public transportMode: string = "transport_mode_walk";
  public routingModes: Array<string> = [];  // routing modes that are currently displayed
  public prevRoutingModes: Array<string> = []; // Route names that have been computed for this locations/parameters
  public availableRoutes: Array<CustomRoute> = []; // Routes that have been computed for this locations/parameters
  private _routingModeChart: string = "routing_mode_distance";
  
  public get routingModeChart(): string {
    return this._routingModeChart;
  }
  
  public set routingModeChart(value: string) {
    // Ensure the value is never undefined or empty
    if (value && value !== 'undefined') {
      this._routingModeChart = value;
    } else {
      this._routingModeChart = "routing_mode_distance";
    }
  }
  private _routingModeDirections: string = "routing_mode_distance";
  
  public get routingModeDirections(): string {
    return this._routingModeDirections;
  }
  
  public set routingModeDirections(value: string) {
    // Ensure the value is never undefined or empty
    if (value && value !== 'undefined') {
      this._routingModeDirections = value;
    } else {
      this._routingModeDirections = "routing_mode_distance";
    }
  }
  public directionsModes: Array<string> = [];
  public selectedChart: 'altitude' | 'green' | 'noise' | 'air' = 'altitude';
  public overlayEnabled: boolean = false;
  public activeSliderMode: 'routing_mode_green' | 'routing_mode_slope' | 'routing_mode_noise' | 'routing_mode_air' | 'routing_mode_distance' | undefined;
  public paramValues = {
    slope: 10,
    green: 50,
    noise: 50,
    air: 50
  };

  private lastCoordinates = {
    fromLat: -1,
    fromLon: -1,
    toLat: -1,
    toLon: -1
  };

  private lastslidervalue = {
    elevation: -1,
    green: -1,
    noise: -1,
    air: -1
  };

  public descriptionOverlay: SafeHtml = this.sanitizer.bypassSecurityTrustHtml(`This overlay combines normalized altitude, green index, noise and PM10 series. Please refer to the data source sections of the individual charts for the underlying data sources.`);
  public descriptionAltitude: SafeHtml = this.sanitizer.bypassSecurityTrustHtml(`Altitude data base on the swiss national geodata api. Click <a href="${config.geoAdminUrl}" target="_blank">here</a> for more info.`);
  public descriptionGreen: SafeHtml = this.sanitizer.bypassSecurityTrustHtml(`Green index data based on greenR. Click <a href="${config.greenRUrl}" target="_blank">here</a> for more info.`);
  public descriptionNoise: SafeHtml = this.sanitizer.bypassSecurityTrustHtml(`Noise data based on swiss national noise map. Click <a href="${config.noiseMapUrl}" target="_blank">here</a> for more info.`);
  // public descriptionAir: SafeHtml = this.sanitizer.bypassSecurityTrustHtml(`Air quality data is requested from IQAir api ant interpolated for the Kanton Zurich. Click <a href="https://www.iqair.com/" target="_blank">here</a> for more info.`);
  public descriptionAir: SafeHtml = this.sanitizer.bypassSecurityTrustHtml(`PM10 data is sourced from OstLuft. Click <a href="${config.ostluftUrl}" target="_blank">here</a> for more info.`);
  // feedback descriptions removed
  
  public loadingRouteCount: number = 0;

  public presetAddress() {
    // insert address of ETH STD
    this.input_from!.setValue({
      city: "Zurich", country: "Switzerland", countrycode: "CH", county: "Switzerland", displayname: "ETH STD, Stampfenbachstrasse , 8006 Zurich",
      district: "Kreis 6", housenumber: '0', id: 0, latitude: 47.3805154, locality: "Unterstrass", longitude: 8.543117562895159, name: "ETH STD", osm_id: 108361353,
      osm_key: "building", osm_type: "W", osm_value: "commercial", postcode: "8006", state: "Zurich", street: "Stampfenbachstrasse", type: "house"
    });

    // insert address of Zürich Stadelhofen
    this.input_to?.setValue({
      city: "Zurich", country: "Switzerland", countrycode: "CH", county: "Switzerland", displayname: "Zürich Stadelhofen, Stadelhoferstrasse 8, 8001 Zurich",
      district: "Altstadt", housenumber: "8", id: 0, latitude: 47.3665643, locality: "Hochschulen", longitude: 8.5483858, name: "Zürich Stadelhofen",
      osm_id: 1239733410, osm_key: "railway", osm_type: "N", osm_value: "station", postcode: "8001", state: "Zurich", street: "Stadelhoferstrasse",
      type: "house"
    });

        this.cdr.detectChanges();
    
    // Call updateField without setTimeout to avoid change detection issues
    this.input_from?.updateField();
    this.input_to?.updateField();
  }

  private showNotificationLoading() {
    this.loadingRouteCount++;
    Swal.fire({
      background: Presets.background,
      color: Presets.textColor,
      imageUrl: "/assets/images/routy.webp",
      imageWidth: 100,
      imageHeight: 100,
      position: "bottom-end",
      title: "computing route",
      allowEscapeKey: false,
      allowOutsideClick: false,
      showConfirmButton: true,
      backdrop: false,
      didOpen: () => { document.body.classList.remove('swal2-shown', 'swal2-height-auto'); } // remove background
    });
    Swal.showLoading();
  }

  private closeNotificationLoading() {
    this.loadingRouteCount--;
    if (this.loadingRouteCount == 0) Swal.close();
  }

  public closeSidebar(): void {
    this.requestCloseSidebar.emit();
  }

  private showErrorNotification(error: string) {
    Swal.fire({
      position: "center",
      html: `${error} <br><br> More detailed information in the web console.`,
      icon: 'error',
      showConfirmButton: true,
      didOpen: () => { document.body.classList.remove('swal2-shown', 'swal2-height-auto'); } // remove background
    });
  }

  public showDataPoint(from: L.LatLng, to: L.LatLng): void {
    //if (!this.chartsVisible) {
    // this.chart_overlay!.addAnnotation(from, to);
    //} else {
    // this.chart_altitude!.addAnnotation(from, to);
    // this.chart_green!.addAnnotation(from, to);
    // this.chart_noise!.addAnnotation(from, to);
    // this.chart_air!.addAnnotation(from, to);
    //}
    this.cdr.detectChanges();
  }

  
  public onChangeControls(): void {
    this.cdr.detectChanges();

    if(this.paramValues.slope !== this.lastslidervalue.elevation) { // if elevation slider value changed
      this.availableRoutes = this.availableRoutes.filter((route) => route.routingMode !== 'routing_mode_slope');
      this.prevRoutingModes = this.prevRoutingModes.filter((mode) => mode !== 'routing_mode_slope');
      this.lastslidervalue.elevation = this.paramValues.slope;
    }
    if(this.paramValues.green !== this.lastslidervalue.green) { // if green index has changed
      this.availableRoutes = this.availableRoutes.filter((route) => route.routingMode !== 'routing_mode_green');
      this.prevRoutingModes = this.prevRoutingModes.filter((mode) => mode !== 'routing_mode_green');
      this.lastslidervalue.green = this.paramValues.green;
    }
    if(this.paramValues.air !== this.lastslidervalue.air) { // if air quality has changed
      this.availableRoutes = this.availableRoutes.filter((route) => route.routingMode !== 'routing_mode_air');
      this.prevRoutingModes = this.prevRoutingModes.filter((mode) => mode !== 'routing_mode_air');
      this.lastslidervalue.air = this.paramValues.air;
    }
    if(this.paramValues.noise !== this.lastslidervalue.noise) { // if noise has changed
      this.availableRoutes = this.availableRoutes.filter((route) => route.routingMode !== 'routing_mode_noise');
      this.prevRoutingModes = this.prevRoutingModes.filter((mode) => mode !== 'routing_mode_noise');
      this.lastslidervalue.noise = this.paramValues.noise;
    }

    // feedback removed

    this.requestRouting(true)

    this.displayRoutes();
    this.cdr.detectChanges();
  }

  public openSliderFor(mode: 'routing_mode_green' | 'routing_mode_slope' | 'routing_mode_noise' | 'routing_mode_air' | 'routing_mode_distance', $event: Event): void {
    $event.preventDefault();
    if (mode === 'routing_mode_distance') {
      this.activeSliderMode = undefined;
      return;
    }
    // Toggle if same mode is already open; otherwise switch to new mode
    this.activeSliderMode = (this.activeSliderMode === mode) ? undefined : mode;
    this.cdr.detectChanges();
  }

  public onSliderMouseUp(): void {
    // Map contextual slider value to underlying parameter and trigger routing update
    if (!this.context_slider) return;
    const val = this.context_slider.selected_value;
    switch (this.activeSliderMode) {
      case 'routing_mode_slope':
        this.paramValues.slope = val;
        break;
      case 'routing_mode_green':
        this.paramValues.green = val;
        break;
      case 'routing_mode_noise':
        this.paramValues.noise = val;
        break;
      case 'routing_mode_air':
        this.paramValues.air = val;
        break;
      default:
        break;
    }
    this.onChangeControls();
  }

  public getIconForMode(mode: string): string {
    switch (mode) {
      case 'routing_mode_slope': return 'landscape';
      case 'routing_mode_green': return 'eco';
      case 'routing_mode_noise': return 'volume_up';
      case 'routing_mode_air': return 'air';
      default: return 'tune';
    }
  }

  public getDefaultForActiveSlider(): number {
    switch (this.activeSliderMode) {
      case 'routing_mode_slope': return this.paramValues.slope;
      case 'routing_mode_green': return this.paramValues.green;
      case 'routing_mode_noise': return this.paramValues.noise;
      case 'routing_mode_air': return this.paramValues.air;
      default: return 50;
    }
  }

  public getMaxForActiveSlider(): number {
    switch (this.activeSliderMode) {
      case 'routing_mode_slope': return 40;
      default: return 100;
    }
  }

  public getLabelForActiveSlider(): string {
    switch (this.activeSliderMode) {
      case 'routing_mode_slope': return 'slope';
      case 'routing_mode_green': return 'green index';
      case 'routing_mode_noise': return 'noise level';
      case 'routing_mode_air': return 'air quality';
      default: return '';
    }
  }

  // Custom routing mode selection helpers (to avoid Material checkmark UI)
  public isRoutingModeActive(mode: string): boolean {
    return this.routingModes.includes(mode);
  }

  public toggleRoutingMode(mode: string, event?: Event): void {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    const idx = this.routingModes.indexOf(mode);
    if (idx >= 0) {
      this.routingModes.splice(idx, 1);
    } else {
      this.routingModes.push(mode);
    }
    this.onChangeControls();
  }

  public setRoutingModeChart(mode: string, event?: Event): void {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    this.routingModeChart = mode;
    this.onChangeSelectedChart();
  }

  public setRoutingModeDirections(mode: string, event?: Event): void {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    this.routingModeDirections = mode;
  }

  public getSliderDescription(): string {
    switch (this.activeSliderMode) {
      case 'routing_mode_slope': return 'Adjust how strongly elevation impacts the route.';
      case 'routing_mode_green': return 'Adjust how strongly green areas are preferred.';
      case 'routing_mode_noise': return 'Adjust how strongly quiet roads are preferred.';
      case 'routing_mode_air': return 'Adjust how strongly low PM10 exposure is preferred.';
      default: return '';
    }
  }

    public flipAddresses(): void {
    if (this.input_from?.value && this.input_to?.value
      && this.input_from.value.id != -1 && this.input_to.value.id != -1) {
      let tmp = this.input_from.value;
      this.input_from.setValue(this.input_to.value);
      this.input_to.setValue(tmp);
    } else if (this.input_from?.value && this.input_from.value.id != -1) {
      this.input_to!.setValue(this.input_from.value);
      this.input_from!.resetField();
    } else if (this.input_to?.value && this.input_to.value.id != -1) {
      this.input_from!.setValue(this.input_to.value);
      this.input_to!.resetField();
    } else {
      return;
    }
    
    this.cdr.detectChanges();
    this.requestRouting();
    
    // Call updateField without setTimeout to avoid change detection issues
    this.input_from?.updateField();
    this.input_to?.updateField();
  }

  public displayRoutes(): void {
    this.map?.clear();
    this.chart_main?.clear();
    this.availableRoutes.forEach((route: CustomRoute) => {
      if (route.transportMode == this.transportMode && this.routingModes.includes(route.routingMode)) {
        this.map?.addRoute(route);
        if (this.overlayEnabled) {
          if (route.routingMode == this.routingModeChart) this.updateOverlay(route);
        } else {
          this.updateCharts(route);
        }
      }
    });

    // Compute available directions modes for current transport and set default selection
    const modesSet = new Set<string>();
    this.availableRoutes.forEach((route: CustomRoute) => {
      if (route.transportMode == this.transportMode) modesSet.add(route.routingMode);
    });
    this.directionsModes = Array.from(modesSet);
    
    // Update routingModeDirections if current selection is no longer valid
    if (!this.directionsModes.includes(this.routingModeDirections)) {
      this.routingModeDirections = this.directionsModes.includes('routing_mode_distance')
        ? 'routing_mode_distance'
        : (this.directionsModes[0] || 'routing_mode_distance');
    }
  }

  public requestRouting(extend: boolean = false): boolean {
    if (!this.input_from?.value || !this.input_to?.value
      || this.input_from.value?.id == -1 || this.input_to?.value?.id == -1) {
      return false;
    }

    if (this.input_from!.value!.latitude == this.lastCoordinates.fromLat
      && this.input_from!.value!.longitude == this.lastCoordinates.fromLon
      && this.input_to!.value!.latitude == this.lastCoordinates.toLat
      && this.input_to!.value!.longitude == this.lastCoordinates.toLon)
      extend = true;

    if (!extend) {
      this.availableRoutes = [];
      this.prevRoutingModes = [];
    }

    this.routingModes.forEach((routingMode: string) => {
      if (!extend || !this.prevRoutingModes.includes(routingMode)) {
        this.showNotificationLoading();
        this.routing.requestRoute(routingMode, {
          // from location
          "fromLat": this.input_from?.value?.latitude || 0,
          "fromLon": this.input_from?.value?.longitude || 0,
          // to location
          "toLat": this.input_to?.value?.latitude || 0,
          "toLon": this.input_to?.value?.longitude || 0,
          // parameters
          "green_index": this.paramValues.green,
          "air": this.paramValues.air,
          "noise": this.paramValues.noise,
          "slope": this.paramValues.slope
        }).then(response => {
          response.forEach((route: CustomRoute) => {
            this.availableRoutes.push(route);
            this.prevRoutingModes.push(route.routingMode);
          });
          this.displayRoutes();
          this.closeNotificationLoading();
        })
          .catch(error => {
            // alert(error.error.error_msg);
            this.closeNotificationLoading();
            this.showErrorNotification(`Failed to request route from server.`);
            console.error("Error requesting route:", error);
        });
      }

      if (extend) {
        this.map?.zoomOut();
      }
    });

    this.lastCoordinates = {
      fromLat: this.input_from?.value?.latitude || 0,
      fromLon: this.input_from?.value?.longitude || 0,
      toLat: this.input_to?.value?.latitude || 0,
      toLon: this.input_to?.value?.longitude || 0
    };

    return true;
  }

  public forceRouteRecalculation(): void {
    // Clear last coordinates to force recalculation
    this.lastCoordinates = {
      fromLat: -1,
      fromLon: -1,
      toLat: -1,
      toLon: -1
    };
    
    // Clear existing routes
    this.availableRoutes = [];
    this.prevRoutingModes = [];
    
    // Trigger new routing
    this.requestRouting(false);
  }

  private updateOverlay(route: CustomRoute) {
    // calculate datasets of route meta data
    let [acc_altitude, acc_noise, acc_green, acc_pm10]: DataPoint[][] = getMetaData(route);
    // console.log([acc_altitude, acc_noise, acc_green, acc_aqius]);
    // normalize data
    [acc_altitude, acc_noise, acc_green, acc_pm10] = normalizeDataPoints([acc_altitude, acc_noise, acc_green, acc_pm10]);
    // smooth data
    [acc_altitude, acc_noise, acc_green, acc_pm10] = smoothDataPoints([acc_altitude, acc_noise, acc_green, acc_pm10]);
    // add datasets to chart
    this.chart_main?.addDataset(route, { name: "altitude", color: getProperties('routing_mode_slope').lineColor, data: acc_altitude });
    this.chart_main?.addDataset(route, { name: "green index", color: getProperties('routing_mode_green').lineColor, data: acc_green });
    this.chart_main?.addDataset(route, { name: "noise", color: getProperties('routing_mode_noise').lineColor, data: acc_noise });
    // this.chart_main?.addDataset(route, { name: "air quality", color: getProperties('routing_mode_air').lineColor, data: acc_aqius });
    this.chart_main?.addDataset(route, { name: "air pollution", color: getProperties('routing_mode_air').lineColor, data: acc_pm10 });
    this.cdr.detectChanges();
  }

  public updateCharts(route: CustomRoute) {
    // calculate datasets of route meta data
    let [acc_altitude, acc_noise, acc_green, acc_pm10]: DataPoint[][] = getMetaData(route);
    // console.log([acc_altitude, acc_noise, acc_green, acc_aqius]);
    // smooth data
    [acc_altitude, acc_noise, acc_green, acc_pm10] = smoothDataPoints([acc_altitude, acc_noise, acc_green, acc_pm10]);
    let color: string = getProperties(route.routingMode).lineColor;
    if (this.selectedChart === 'altitude') this.chart_main?.addDataset(route, { name: route.routingMode, color: color, data: acc_altitude });
    if (this.selectedChart === 'green') this.chart_main?.addDataset(route, { name: route.routingMode, color: color, data: acc_green });
    if (this.selectedChart === 'noise') this.chart_main?.addDataset(route, { name: route.routingMode, color: color, data: acc_noise });
    if (this.selectedChart === 'air') this.chart_main?.addDataset(route, { name: route.routingMode, color: color, data: acc_pm10 });
    this.cdr.detectChanges();
  }

  public onChangeSelectedChart(): void {
    // ensure routingModeChart is valid for accumulated view
    if (this.overlayEnabled) {
      if (!this.routingModes.includes(this.routingModeChart)) {
        // pick first available routing mode if current selection is not active
        this.routingModeChart = this.routingModes[0] || 'routing_mode_distance';
      }
    }
    // defer rebuild until after child inputs update
    setTimeout(() => {
      this.chart_main?.clear();
      let anyPlotted = false;
      this.availableRoutes.forEach((route: CustomRoute) => {
        if (route.transportMode == this.transportMode && this.routingModes.includes(route.routingMode)) {
          if (this.overlayEnabled) {
            if (route.routingMode == this.routingModeChart) {
              this.updateOverlay(route);
              anyPlotted = true;
            }
          } else {
            this.updateCharts(route);
            anyPlotted = true;
          }
        }
      });
      // fallback: if nothing matched (e.g., no active modes), show first available route metric
      if (!anyPlotted && this.availableRoutes.length > 0) {
        const fallback = this.availableRoutes[0];
        if (this.overlayEnabled) {
          this.updateOverlay(fallback);
        } else {
          this.updateCharts(fallback);
        }
      }
      this.cdr.detectChanges();
    }, 0);
  }

  public toggleMetrics(): void {
    this.metricsVisible = !this.metricsVisible;
    if (this.metricsVisible) {
      // ensure only one section is open at a time
      this.directionsVisible = false;
      setTimeout(() => this.onChangeSelectedChart(), 100);
    }
  }

  public collapseDirections(): void {
    this.directionsVisible = !this.directionsVisible;
    if (this.directionsVisible) {
      // ensure only one section is open at a time
      this.metricsVisible = false;
    }
  }

  public openProjectInfo(): void {
    if (this.map) {
      this.map.openProjectInfo();
    }
  }

  public getColorForRoutingMode(routingMode: string): string {
    return getProperties(routingMode).lineColor;
  }

  public getDirectionsData() {
    if (this.availableRoutes.length <= 0)
      return [];

    var directions = this.availableRoutes[0].directions;
    this.availableRoutes.forEach((route: CustomRoute) => {
      if (route.transportMode == this.transportMode && route.routingMode == this.routingModeDirections) {
        directions = route.directions;
      }
    });

    const directionsSimple = directions.map(direction => ({
      cardinalDirection: direction.cardinalDirection,
      distance: Math.round(direction.distance),
      name: direction.name,
      id: direction.edges[0]
    }));

    //Simplify multiple directions with the same name and cardinal direction to one
    const directionsReduced = directionsSimple.reduce((acc: { cardinalDirection: string, distance: number, name: string, id: number }[], cur) => {
      const existing = acc.pop();
      if (existing && (existing.cardinalDirection === cur.cardinalDirection)) {
        existing.distance += cur.distance;
        acc.push(existing);
      } else {
        if(existing)
          if(existing.distance >= 10) 
          acc.push(existing);
          else{
            const preprevious = acc.pop();
            if(preprevious){
              preprevious.distance += existing.distance;
              acc.push(preprevious);
            }
          }
        acc.push(cur);
      }
      return acc;
    }, []);

    return directionsReduced;
  }

  public goToEdge(id: number): void {
    const route = this.availableRoutes.find(route => route.edges.some(edge => edge.id === id));
    if (route) {
      const edge = route.edges.find(edge => edge.id === id);
      if (edge) {
        const latlng = L.latLng(edge.source.lat, edge.source.lon);
        this.map?.indicatePosition(latlng);
      }
    }
  }

  public isMobile(): boolean {
    return window.innerWidth <= 768;
  }
}
