import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { catchError } from 'rxjs/operators';

interface VersionInfo {
  version: string;
  gitHash: string;
  buildDate: string;
}

@Injectable({
  providedIn: 'root'
})
export class VersionService {
  private versionUrl = 'assets/version.json';

  constructor(private http: HttpClient) {}

  getVersion(): Observable<VersionInfo> {
    return this.http.get<VersionInfo>(this.versionUrl).pipe(
      // Handle errors gracefully by providing default values
      catchError(() => {
        console.warn('Failed to load version info, using defaults');
        return of({
          version: 'dev_local',
          gitHash: 'unknown',
          buildDate: new Date().toISOString()
        });
      })
    );
  }
}