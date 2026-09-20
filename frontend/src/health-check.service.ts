import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable, interval, switchMap, catchError, of } from 'rxjs';
import { BackendService } from './backend.service';

/**
 * Service for monitoring backend health status.
 * Provides periodic health checks and status updates.
 */
@Injectable({
  providedIn: 'root'
})
export class HealthCheckService {
  private healthCheckInterval = 5000; // Check every 5 seconds
  private isOnlineSubject = new BehaviorSubject<boolean>(true);
  private isCheckingSubject = new BehaviorSubject<boolean>(false);
  
  public isOnline$: Observable<boolean> = this.isOnlineSubject.asObservable();
  public isChecking$: Observable<boolean> = this.isCheckingSubject.asObservable();

  constructor(private http: HttpClient, private backend: BackendService) {
    this.startHealthCheck();
  }

  /**
   * Starts the periodic health check process.
   */
  private startHealthCheck(): void {
    interval(this.healthCheckInterval)
      .pipe(
        switchMap(() => this.checkBackendHealth())
      )
      .subscribe();
  }

  /**
   * Performs a health check on the backend.
   * @returns Observable<boolean> indicating if backend is online
   */
  private checkBackendHealth(): Observable<boolean> {
    this.isCheckingSubject.next(true);
    
    return this.http.get(this.backend.buildUrl('/status/')).pipe(
      catchError((error) => {
        console.warn('Backend health check failed:', error);
        this.isOnlineSubject.next(false);
        this.isCheckingSubject.next(false);
        return of(false);
      }),
      switchMap((response) => {
        const isOnline = response !== null && response !== false;
        this.isOnlineSubject.next(isOnline);
        this.isCheckingSubject.next(false);
        return of(isOnline);
      })
    );
  }

  /**
   * Manually triggers a health check.
   */
  public triggerHealthCheck(): void {
    this.checkBackendHealth().subscribe();
  }

  /**
   * Gets the current online status.
   */
  public get isOnline(): boolean {
    return this.isOnlineSubject.value;
  }

  /**
   * Gets the current checking status.
   */
  public get isChecking(): boolean {
    return this.isCheckingSubject.value;
  }
}
