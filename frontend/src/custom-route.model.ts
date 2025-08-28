import { DataPoint } from "./app/custom-chart/data-point.model";
import { CustomEdge } from "./custom-edge.model";
import { CustomVertex } from "./custom-vertex.model";
import { CustomDirection } from "./custom-direction.model";

export interface CustomRoute {
    vertices: CustomVertex[];
    edges: CustomEdge[];
    startVertex: CustomVertex;
    endVertex: CustomVertex;
    routingMode: string;
    transportMode: string;
    directions: CustomDirection[];
}

export interface Properties {
    lineColor: string;
    chartLabel: string;
}

const configuration: { [key: string]: Properties } = {
    'routing_mode_distance': {
        lineColor: '#CB2B3E',
        chartLabel: 'distance'
    },
    'routing_mode_slope': {
        lineColor: '#2A81CB',
        chartLabel: 'slope'
    },
    'routing_mode_green': {
        lineColor: '#00d8ac',
        chartLabel: 'green-index'
    },
    'routing_mode_noise': {
        lineColor: '#990099',
        chartLabel: 'noise'
    },
    'routing_mode_air': {
        lineColor: '#FFBF00',
        chartLabel: 'air'
    },
    'routing_mode_traffic': {
        lineColor: '#0B00D3',
        chartLabel: 'traffic'
    },
    'routing_mode_feedback_twa' : {
        lineColor: '#ff5733',
        chartLabel: 'feedback-ci'
    },
    'routing_mode_feedback_ci' : {
        lineColor: '#75ff33',
        chartLabel: 'feedback-twa'
    }
}

export function getProperties(routingMode: string): Properties {
    if(!configuration[routingMode]) throw Error("INVALID_ROUTING_TYPE");
    return configuration[routingMode];
}

export function getEdgeOsmIds(route: CustomRoute): number[] {
    let osmIds: number[] = [];
    route.edges.forEach((edge: CustomEdge) => {
        osmIds.push(edge.osmId);
    });
    return removeDups(osmIds)
}

/**
* Construct a copy of an array with duplicate items removed.
* Where duplicate items exist, only the first instance will be kept.
*/
function removeDups<T>(array: T[]): T[] {
   return [...new Set(array)];
};

export function avgGreenIndex(route: CustomRoute) {
    let accGreenIndex: number = 0;
    let filtered = route.edges.filter((edge: CustomEdge) => edge.greenIndex >= 0);
    filtered.forEach((edge: CustomEdge) => {
        accGreenIndex += edge.greenIndex;
    });
    return accGreenIndex / filtered.length;
}

export function avgSlope(route: CustomRoute) {
    let accSlope: number = 0;
    let filtered = route.edges.filter((edge: CustomEdge) => edge.slope >= 0);
    filtered.forEach((edge: CustomEdge) => {
        accSlope += edge.slope;
    });
    return accSlope / filtered.length;
}

// Removed AQI aggregation in favour of PM10-only

export function avgNoise(route: CustomRoute) {
    let accNoise: number = 0;
    let filtered = route.edges.filter((edge: CustomEdge) => edge.noise >= 0);
    filtered.forEach((edge: CustomEdge) => {
        accNoise += edge.noise;
    });
    return accNoise / filtered.length;
}

export function avgPm10(route: CustomRoute) {
    let accPm10: number = 0;
    let filtered = route.edges.filter((edge: CustomEdge) => edge.pm_10 >= 0);
    filtered.forEach((edge: CustomEdge) => {
        accPm10 += edge.pm_10;
    });
    return accPm10 / filtered.length;
}

export function getMetaData(route: CustomRoute): DataPoint[][] {
    // first Vertex is first vertex that contains metadata (startVertex is only dummy vertex)
    let firstVertex = route.vertices[0];
    let distance = 0;

    // initialize DataPoint[] with value of first data vertex
    let altitude: DataPoint[] = [[distance, firstVertex.altitude, firstVertex.lat, firstVertex.lon]];
    let noise: DataPoint[] = [[distance, firstVertex.noise, firstVertex.lat, firstVertex.lon]];
    let greenIndex: DataPoint[] = [];
    let pm10: DataPoint[] = [];

    route.edges.forEach((edge: CustomEdge) => {
        let target: CustomVertex = edge.target;
        
        // set values held by edge object to previous distance because edge starts at previous distance
        greenIndex.push([distance, edge.greenIndex, target.lat, target.lon]);
        pm10.push([distance, edge.pm_10, target.lat, target.lon]);

        distance += edge.distance;

        // set values held by target vertex (values of first vertex already set)
        altitude.push([distance, target.altitude, target.lat, target.lon]);
        noise.push([distance, target.noise, target.lat, target.lon]);
    });

    return [altitude, noise, greenIndex, pm10];
}