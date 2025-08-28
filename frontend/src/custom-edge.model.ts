import { CustomVertex } from "./custom-vertex.model";
import { config } from './app/config';

export interface CustomEdge {
    osmId: number;
    source: CustomVertex;
    target: CustomVertex;
    distance: number;
    bearing: number;
    maxspeed: number;
    cardinalDirection: string;
    slope: number;
    greenIndex: number;
    traveltime: { transport_mode_cycle: number, transport_mode_walk: number, transport_mode_drive: number };
    noise: number;
    id: number;
    tags: Object[];
    highway: string;
    pm_10: number;
}

export function generateHtmlTableForCustomEdge(customEdge: CustomEdge): string {
  const { source, target } = customEdge;
  // Start building the HTML string for the table
  let html = `<table border="1" style="border-collapse: collapse; border: solid 1px black;">
      <tr>
        <th>Property</th>
        <th>Value</th>
      </tr>
      <tr>
        <td>highway</td>
        <td>${customEdge.highway}</td>
      </tr>
      <tr>
        <td>OSM ID</td>
        <td><a href="${config.openstreetmapUrl}/way/${customEdge.osmId}" target="_blank">way/${customEdge.osmId}</a></td>
      </tr>
      <tr>
        <td>Source Vertex (OSM ID, Altitude, Noise)</td>
        <td><a href="${config.openstreetmapUrl}/node/${source.osmId}" target="_blank">node/${source.osmId}</a>, ${source.altitude}, ${source.noise}</td>
      </tr>
      <tr>
        <td>Target Vertex (OSM ID, Altitude, Noise)</td>
        <td><a href="${config.openstreetmapUrl}/node/${target.osmId}" target="_blank">node/${target.osmId}</a>, ${target.altitude}, ${target.noise}</td>
      </tr>
      <tr>
        <td>Slope</td>
        <td>${(customEdge.slope * 100).toFixed(2)} %</td>
      </tr>
      <tr>
        <td>Distance</td>
        <td>${customEdge.distance.toFixed(2)} m</td>
      </tr>
      <tr>
        <td>Noise</td>
        <td>${customEdge.noise.toFixed(2)} db</td>
      </tr>
      <tr>
        <td>Green Index</td>
        <td>${customEdge.greenIndex.toFixed(2)}</td>
      </tr>
      <tr>
        <td>PM 10</td>
        <td>${customEdge.pm_10.toFixed(2)}</td>
      </tr>
      <tr>
        <td>Cardinal Direction</td>
        <td>${customEdge.cardinalDirection}</td>
      </tr>
      <tr>
        <td>routify-id</td>
        <td>${customEdge.id}</td>
      </tr>
    </table>`;

  return html;
}