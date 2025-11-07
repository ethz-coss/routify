import { Injectable } from '@angular/core';
import { Observable, of } from 'rxjs';
import { delay, map } from 'rxjs/operators';
import { HttpClient } from '@angular/common/http';
import { config } from './app/config';

export interface Feature {
    id: number;
    latitude: number;
    longitude: number
    osm_id: number;
    country: string;
    city: string;
    countrycode: string;
    postcode: string;
    locality: string;
    county: string;
    type: string;
    osm_type: string;
    osm_key: string;
    housenumber: string;
    street: string;
    district: string;
    osm_value: string;
    name: string;
    state: string;
    displayname: string;
}

@Injectable({
    providedIn: 'root'
})
export class AutoCompleteService {
    
    constructor(private http: HttpClient) { }
    
    private resolvePhotonUrl(): string {
        // Always use relative path /photon/ - nginx proxies it locally, Caddy handles it in production
        // This avoids CORS issues in local development
        return '/photon/';
    }
    
    async getFeatures(term: string = ""): Promise<Observable<Feature[]>> {
        // let items = getMockFeatures();
        let items = await this.requestSuggestions(term);
        return of(items).pipe(delay(500));
    }

    async requestAddress(input: L.LatLng) {
        if(!input) throw Error("AUTOCOMPLETE_INVALID_COORDINATES");
        
        // Just return the exact coordinates - backend will find nearest vertex for pathfinding
        return {
            'id': 0,
            'latitude': input.lat,
            'longitude': input.lng,
            'osm_id': -1, // No OSM ID for custom coordinates
            'country': '',
            'city': '',
            'countrycode': '',
            'postcode': '',
            'locality': '',
            'county': '',
            'type': '',
            'osm_type': '',
            'osm_key': '',
            'housenumber': '',
            'street': '',
            'district': '',
            'osm_value': '',
            'name': '',
            'state': '',
            'displayname': `${input.lat.toFixed(6)}, ${input.lng.toFixed(6)}`
        };
    }

    async requestSuggestions(input: string): Promise<Feature[]> {
        if(!input) return [];
        
        const photonUrl = this.resolvePhotonUrl();
        const url: string = `${photonUrl}api?q=${encodeURIComponent(input)}&lat=47.382215169614895&lon=8.537124125464356`;

        try {
            const response = await fetch(url);
            if (!response.ok) {
                console.error('Photon API error:', response.status, response.statusText);
                return [];
            }
            const data = await response.json();
            
            let id = 0;
            let features: Feature[] = [];
            if (data.features && Array.isArray(data.features)) {
                data.features.forEach((el: any) => {
                    features.push({
                        'id': id,
                        'latitude': el.geometry.coordinates[1],
                        'longitude': el.geometry.coordinates[0],
                        'osm_id': el.properties.osm_id,
                        'country': el.properties.country,
                        'city': el.properties.city,
                        'countrycode': el.properties.countrycode,
                        'postcode': el.properties.postcode,
                        'locality': el.properties.locality,
                        'county': el.properties.country,
                        'type': el.properties.type,
                        'osm_type': el.properties.osm_type,
                        'osm_key': el.properties.osm_key,
                        'housenumber': el.properties.housenumber,
                        'street': el.properties.street,
                        'district': el.properties.district,
                        'osm_value': el.properties.osm_value,
                        'name': el.properties.name,
                        'state': el.properties.state,
                        'displayname': `${value(el.properties.name)}, ${value(el.properties.street)} ${value(el.properties.housenumber)}, ${value(el.properties.postcode)} ${value(el.properties.city)}`
                    });
                    id++;
                });
            }
            
            const filteredFeatures = features.filter(el => el.state == 'Zurich' || el.state == 'Zürich');
            return filteredFeatures;
        } catch (error) {
            console.error('Error fetching Photon suggestions:', error);
            return [];
        }
    }
}

function value(val: string) {
    return (val) ? val : ""
}

function getMockFeatures() {
    return [
        {
            'latitude': 47.3804392,
            'longitude': 8.5429165,
            'osm_id': 3223113075,
            'country': "Schweiz/Suisse/Svizzera/Svizra",
            'city': "Zürich",
            'countrycode': "CH",
            'postcode': "8006",
            'locality': "Unterstrass",
            'county': "Bezirk Zürich",
            'type': "house",
            'osm_type': "N",
            'osm_key': "place",
            'housenumber': "48",
            'street': "Stampfenbachstrasse",
            'district': "Kreis 6",
            'osm_value': "house",
            'name': "ETH STD",
            'state': "Zürich",
            "displayname": "ETH STD, Stampfenbachstrasse 48"
        },
        {
            'latitude': 47.3804392,
            'longitude': 8.5429165,
            "osm_id": 3707771106,
            'country': "Schweiz/Suisse/Svizzera/Svizra",
            'city': "Zürich",
            'countrycode': "CH",
            'postcode': "8006",
            'locality': "Unterstrass",
            'county': "Bezirk Zürich",
            'type': "house",
            'osm_type': "N",
            'osm_key': "office",
            'housenumber': "48",
            'street': "Stampfenbachstrasse",
            'district': "Kreis 6",
            'osm_value': "research",
            'name': "Disney Research Zürich",
            'state': "Zürich",
            "displayname": "Disney Research Zürich, Stampfenbachstrasse 48"
        }
    ]
}
