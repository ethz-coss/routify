import { RouteMetaData } from "./route-meta-data.model";

export interface Route {
    id: string;
    transport_mode: string;
    routing_mode: string;
    distance_meters: number;
    meta_data: RouteMetaData;
    osm_id_list: number[];
    traveltime_seconds: number;
}
