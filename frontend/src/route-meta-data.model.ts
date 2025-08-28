import { RouteDataPoint } from "./route-data-point.model";

export interface RouteMetaData {
    avg_noise_db: number;
    avg_altitude: number;
    data: Array<RouteDataPoint>;
    max_altitude: number;
    min_altitude: number;
    max_greenindex: number;
    max_elevation_relative: number;
    avg_greenindex: number;
    min_elevation_relative: number;
    avg_elevation_relative: number;
    min_noise_db: number;
    max_noise_db: number;
    min_greenindex: number;
}