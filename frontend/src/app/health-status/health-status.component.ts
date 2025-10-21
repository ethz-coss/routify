import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subscription } from 'rxjs';
import { HealthCheckService } from '../../health-check.service';
import Swal from 'sweetalert2';

@Component({
  selector: 'app-health-status',
  standalone: true,
  imports: [CommonModule],
  template: `
    <!-- This component doesn't need a template as it uses SweetAlert2 -->
  `,
  styles: []
})
export class HealthStatusComponent implements OnInit, OnDestroy {
  private subscriptions: Subscription[] = [];
  private alertShown = false;
  private alertInstance: any = null;

  constructor(private healthCheckService: HealthCheckService) {}

  ngOnInit(): void {
    // Subscribe to health status changes
    this.subscriptions.push(
      this.healthCheckService.isOnline$.subscribe(isOnline => {
        this.handleHealthStatusChange(isOnline);
      })
    );
  }

  ngOnDestroy(): void {
    this.subscriptions.forEach(sub => sub.unsubscribe());
    this.closeAlert();
  }

  private handleHealthStatusChange(isOnline: boolean): void {
    if (!isOnline && !this.alertShown) {
      this.showOfflineAlert();
    } else if (isOnline && this.alertShown) {
      this.showOnlineAlert();
    }
  }

  private showOfflineAlert(): void {
    this.alertShown = true;
    this.alertInstance = Swal.fire({
      title: 'Backend Offline',
      text: 'Waiting for backend to come online...',
      icon: 'warning',
      position: 'top-start',
      toast: true,
      showConfirmButton: false,
      allowOutsideClick: false,
      allowEscapeKey: false,
      showCloseButton: false,
      didOpen: () => {
        // Add custom styling for the alert
        const popup = Swal.getPopup();
        if (popup) {
          popup.style.cssText = `
            position: fixed !important;
            top: 20px !important;
            left: 20px !important;
            z-index: 9999 !important;
            background: #f8f9fa !important;
            border: 1px solid #dc3545 !important;
            border-radius: 8px !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important;
          `;
        }
      }
    });
  }

  private showOnlineAlert(): void {
    if (this.alertInstance) {
      this.alertInstance.close();
      this.alertInstance = null;
    }
    
    this.alertShown = false;
    
    // Show a brief success message
    Swal.fire({
      title: 'Backend Online',
      text: 'Connection restored!',
      icon: 'success',
      position: 'top-start',
      toast: true,
      showConfirmButton: false,
      timer: 2000,
      timerProgressBar: true
    });
  }

  private closeAlert(): void {
    if (this.alertInstance) {
      this.alertInstance.close();
      this.alertInstance = null;
    }
    this.alertShown = false;
  }
}
