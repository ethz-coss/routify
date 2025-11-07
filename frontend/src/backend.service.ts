import { Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { CustomEdge } from './custom-edge.model';
import { CustomRoute } from './custom-route.model';
import { config } from './app/config';

@Injectable({
    providedIn: 'root'
})
export class BackendService {
    httpOptions: any;
    activeBackendUrl: string;
    
    constructor(private http: HttpClient) {
        this.activeBackendUrl = this.resolveBackendUrl();
        this.httpOptions = {
            observe: 'body', 
            responseType: 'json',
            headers: new HttpHeaders({ 
              'Access-Control-Allow-Origin' : '*'
            })
        };
    }

    async requestRoute(mode: string, data: Object): Promise<CustomRoute[]> {
        const url = this.buildUrl(`/route/${mode}/`);

        return await firstValueFrom(this.http.post(url, data, this.httpOptions)) as unknown as CustomRoute[];
    }

    async requestBoundary() {
        const url = this.buildUrl('/status/boundary/');

        try {
            const response = await firstValueFrom(this.http.get(url));
            return response;
        } catch (error) {
            return null;
        }    
    }

    // feedback/rating removed

    async queryFeatures(latlng: L.LatLng): Promise<CustomEdge[]> {
        const url = this.buildUrl('/query/nearby/');

        let params = new HttpParams()
        .set('lat', latlng.lat.toString())
        .set('lon', latlng.lng.toString());

        return (await firstValueFrom(this.http.get(url, { params })) as CustomEdge[]);
    }

    private resolveBackendUrl(): string {
        if (typeof window === 'undefined') {
            return config.backendUrl;
        }

        const hostname = window.location.hostname;
        const isLocalHost = hostname === 'localhost' || hostname === '127.0.0.1';

        // For localhost, use direct backend URL; for production, use relative paths (empty string)
        return isLocalHost ? config.backendUrl : '';
    }

    private buildUrl(path: string): string {
        if (!this.activeBackendUrl) {
            return path.startsWith('/') ? path : `/${path}`;
        }
        return `${this.activeBackendUrl}${path}`;
    }
}
