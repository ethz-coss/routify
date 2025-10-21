import { AfterViewInit, ChangeDetectorRef, Component, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import * as L from 'leaflet';
// import custom components
import { MapComponent } from '../map/map.component';
import { ControlsComponent } from '../controls/controls.component';
import { HealthStatusComponent } from '../health-status/health-status.component';
import Swal from 'sweetalert2';
import { Presets } from '../global-presets';
import { VersionService } from 'src/version.service';

@Component({
  selector: 'app-base',
  standalone: true,
  imports: [
    CommonModule,
    // import custom components
    MapComponent,
    ControlsComponent,
    HealthStatusComponent
  ],
  templateUrl: './base.component.html',
  styleUrl: './base.component.css'
})

export class BaseComponent implements AfterViewInit {
  sidebarOpen: boolean = true;
  background: string = Presets.background;
  private lastSidebarShiftPixels: number = 0; // Store the shift value in pixels
  private initialMapWidth: number = 0; // Store initial map width
  private initialMapBounds: any = null; // Store initial map bounds
  private initialLngPerPixel: number = 0; // Store initial longitude per pixel

  @ViewChild('map') map!: MapComponent;

  constructor(private cdr: ChangeDetectorRef, private versionService: VersionService) {}

  async ngAfterViewInit(): Promise<void> {
    // // welcome screen by Routy (only in deployment)
    // await Swal.fire({
    //   background: Presets.background,
    //   color: Presets.textColor,
    //   title: "Hi there!",
    //   text: "I'm Routy, your friendly guide. Welcome to Routify! I'll help you find the perfect path just for you. Let's get started!",
    //   imageUrl: "/assets/images/routy.webp",
    //   imageWidth: 400,
    //   imageHeight: 400,
    //   confirmButtonColor: Presets.accentColor,
    //   confirmButtonText: "Let's Go!"
    // });
    this.versionService.getVersion().subscribe(data => {
      // Version info loaded: ${data.gitHash}, ${data.buildDate}
    });
  }
  
  public closeSidebar(): void {
    this.sidebarOpen = false;
    this.cdr.detectChanges();
    
    // Invalidate map size after sidebar closes to ensure tiles load properly
    if (this.map && this.map.map) {
      setTimeout(() => {
        this.map.map.invalidateSize();
      }, 350); // Delay to account for CSS transition (0.3s) plus buffer
    }
  }

  public openSidebar(): void {
    this.sidebarOpen = true;
    this.cdr.detectChanges();
    
    // Invalidate map size after sidebar opens to ensure tiles load properly
    if (this.map && this.map.map) {
      setTimeout(() => {
        this.map.map.invalidateSize();
      }, 350); // Delay to account for CSS transition (0.3s) plus buffer
    }
  }
}
