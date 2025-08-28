import { Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { isDevMode } from '@angular/core';
import { CustomEdge } from './custom-edge.model';
import { CustomRoute } from './custom-route.model';
import { config } from './app/config';

@Injectable({
    providedIn: 'root'
})
export class BackendService {
    httpOptions: any;
    isLocal: boolean = config.isLocal;
    activeBackendUrl: string = this.buildBackendUrl();
    
    constructor(private http: HttpClient) {
        this.httpOptions = {
            observe: 'body', 
            responseType: 'json',
            headers: new HttpHeaders({ 
              'Access-Control-Allow-Origin' : '*'
            })
        };
    }

    private buildBackendUrl(): string {
        return this.isLocal
            ? config.localBackendUrl
            : (config.isDevMode ? config.devBackendUrl : config.backendUrl);
    }

    toggleLocal() {
        this.isLocal = !this.isLocal
        this.activeBackendUrl = this.buildBackendUrl();
        return this.isLocal
    }

    async requestRoute(mode: string, data: Object): Promise<CustomRoute[]> {
        const url: string = `${this.activeBackendUrl}/route/${mode}/`;

        return await firstValueFrom(this.http.post(url, data, this.httpOptions)) as unknown as CustomRoute[];
    }

    async requestBoundary() {
        const url: string = `${this.activeBackendUrl}/status/boundary/`;

        try {
            const response = await firstValueFrom(this.http.get(url));
            return response;
        } catch (error) {
            return null;
        }    
    }

    // feedback/rating removed

    async queryFeatures(latlng: L.LatLng): Promise<CustomEdge[]> {
        const url: string = `${this.activeBackendUrl}/query/nearby/`;

        let params = new HttpParams()
        .set('lat', latlng.lat.toString())
        .set('lon', latlng.lng.toString());

        return (await firstValueFrom(this.http.get(url, { params })) as CustomEdge[]);
    }
}