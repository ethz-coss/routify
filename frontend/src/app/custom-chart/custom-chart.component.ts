import { AfterViewInit, ChangeDetectorRef, Component, Input, OnInit, ViewChild, OnChanges, SimpleChanges } from "@angular/core";
import * as L from 'leaflet';

import {
  ChartComponent,
  ApexAxisChartSeries,
  ApexChart,
  ApexXAxis,
  ApexDataLabels,
  ApexStroke,
  ApexYAxis,
  ApexTitleSubtitle,
  ApexLegend,
  NgApexchartsModule,
  ApexAnnotations
} from "ng-apexcharts";
import { RouteDataPoint } from "src/route-data-point.model";
import { Route } from "src/route.model";
import { MapComponent } from "../map/map.component";
import { SafeHtml } from "@angular/platform-browser";
import { kernelSmooth, medianFilter } from "./statistical-tools";
import { DataPoint } from "./data-point.model";
import { winsorizeDataPoints } from "./statistical-tools";
import { CustomRoute } from "src/custom-route.model";
import { CustomVertex } from "src/custom-vertex.model";

export type ChartOptions = {
  series: ApexAxisChartSeries;
  chart: ApexChart;
  xaxis: ApexXAxis;
  annotations: ApexAnnotations;
  stroke: ApexStroke;
  dataLabels: ApexDataLabels;
  yaxis: ApexYAxis;
  title: ApexTitleSubtitle;
  labels: string[];
  legend: ApexLegend;
  subtitle: ApexTitleSubtitle;
};

@Component({
  selector: 'app-custom-chart',
  standalone: true,
  imports: [
    NgApexchartsModule
  ],
  templateUrl: './custom-chart.component.html',
  styleUrl: './custom-chart.component.css'
})
export class CustomChartComponent implements OnInit, AfterViewInit, OnChanges {
  @ViewChild("chart", { static: false }) chart: ChartComponent | undefined;
  public chartOptions: any;
  public descriptionVisible: boolean = false;

  @Input() title: string = "";
  @Input() info: string = "chart-description";
  @Input() description: SafeHtml = "chart-description";
  @Input() map?: MapComponent;
  @Input() precision?: number;

  private routes_displayed: CustomRoute[] = [];

  ngOnInit(): void {
    this.chartOptions.title.text = this.title;
  }

  ngOnChanges(changes: SimpleChanges): void {
    // Keep chart options in sync if inputs change after initialization
    if (this.chart) {
      this.chart.updateOptions({
        title: { text: this.title },
        yaxis: {
          decimalsInFloat: this.precision,
          type: 'numeric',
          title: { text: this.info },
          tickAmount: 10,
          opposite: false,
          tooltip: { enabled: false }
        }
      }, false, true);
      this.cdr.detectChanges();
    } else {
      this.chartOptions.title.text = this.title;
    }
  }

  public toggleVisibilityDescription() {
    this.descriptionVisible = !this.descriptionVisible;
    setTimeout(() => {
      this.descriptionVisible = false;
      this.cdr.detectChanges();
    }, 5000);
    this.cdr.detectChanges();
  }

  // private getDataPoint(latlngs: L.LatLng): CustomVertex {
  //   this.routes_displayed.forEach((route: CustomRoute) => {
  //     let dataPoint = route.vertices.find((vertex: CustomVertex) =>
  //       +vertex.lat === +latlngs.lat &&
  //       +vertex.lon === +latlngs.lng
  //     );
  //     if (dataPoint) { return dataPoint; }
  //   });
  //   return;
  //   // throw new Error("UNKNOWN_DATA_POINT");
  // }

  // public addAnnotation(from: L.LatLng, to: L.LatLng) {
  //   let dp_from: RouteDataPoint | undefined = this.getDataPoint(from);
  //   let dp_to: RouteDataPoint | undefined = this.getDataPoint(to);
  //   if(dp_from && dp_to) {
  //     this.chart?.clearAnnotations();
  //     this.chart?.addXaxisAnnotation({
  //       x: dp_from!.distance_meters, // from x position
  //       x2: dp_to!.distance_meters, // to x2 position
  //       fillColor: '#e0e0e0',
  //       opacity: 0.8,
  //     });
  //     setTimeout(() => this.chart?.clearAnnotations(), 2000);
  //   }
  // }

  // dataset ist array of [x, y, lat, lon] (where x is distance from origin and y is value)
  public addDataset(route: CustomRoute, dataset: {name:string, color: string, data: DataPoint[]}): void {
    this.routes_displayed.push(route);
    this.chartOptions.series.push(dataset);
    if (this.chart) {
      this.chart.updateSeries(this.chartOptions.series, true);
    } else {
      console.error('ApexCharts instance not found');
    }
  
    // Manually trigger change detection if necessary
    this.cdr.detectChanges();
  }

  public clear() {
    this.chart?.clearAnnotations();
    this.routes_displayed = [];
    this.chartOptions.series = [];
    this.chart?.updateSeries(this.chartOptions.series, true);
  }

  private getFilenameWithDateTime(prefix: string, extension: string): string {
    const now = new Date();
    const date = now.toISOString().slice(0,10); // Format: YYYY-MM-DD
    const time = now.toTimeString().slice(0,8).replace(/:/g, '-'); // Format: HH-MM-SS
    return `${prefix}_${date}_${time}.${extension}`;
  }  

  constructor(private cdr: ChangeDetectorRef) {
    this.chartOptions = {
      series: [ ], // DataPoint[]
      chart: {
        type: "line",
        height: 300,
        zoom: { enabled: true },
        toolbar: {
          tools: {
          },
          export: {
            csv: {
              filename: this.getFilenameWithDateTime('coss_maps_export', ''),
              columnDelimiter: ',',
              headerCategory: 'distance_from_origin',
              headerValue: 'value'
            },
            svg: {
              filename: this.getFilenameWithDateTime('coss_maps_export', ''),
            },
            png: {
              filename: this.getFilenameWithDateTime('coss_maps_export', ''),
            }
          }
        }
      },
      tooltip: {
        enabled: true,
        // event triggered on hover of tooltip
        custom: (e: any) => {
          let lat: number = e.w.config.series[e.seriesIndex].data[e.dataPointIndex][2]; // latitude of datapoint
          let lon: number = e.w.config.series[e.seriesIndex].data[e.dataPointIndex][3]; // longitude of datapoint
          // indicate hovered datapoint on map
          this.map?.indicatePosition(L.latLng([lat, lon]));
          return "" // e.series[e.seriesIndex][e.dataPointIndex];
        },
        marker: {
          show: false,
          size: 2
        }
      },
      markers: {
        show: false,
      },
      dataLabels: {
        enabled: false
      },
      stroke: {
        curve: "smooth", // change to smooth to reduce sharpness
        width: 2
      },
      title: {
        text: this.title,
        align: "left"
      },
      xaxis: {
        type: 'numeric',
        title: {
          text: "distance from origin [m]"
        },
        tickAmount: 8,
        tooltip: {
          enabled: false,
        },
      },
      yaxis: {},
      legend: {
        horizontalAlign: "left"
      }
    };
  }

  ngAfterViewInit(): void {
    setTimeout(() => {
      this.chart?.updateOptions({
        yaxis: {
          decimalsInFloat: this.precision,
          type: 'numeric',
          title: {
            text: this.info
          },
          tickAmount: 10,
          opposite: false,
          tooltip: {
            enabled: false,
          },
        },
      }, false, true);
    }, 50);
  }
}
