import { kernelSmooth, medianFilter, winsorizeDataPoints } from "./statistical-tools";

export type DataPoint = [number, number, number, number]; // [x, y, lat, lon]

export function dpMin(datapoints: DataPoint[]): number {
    let min: number = 0;
    datapoints.forEach((dp: DataPoint) => {
        min = Math.min(min, dp[1]);
    });
    return min;
}

export function dpMax(datapoints: DataPoint[]): number {
    let max: number = 0;
    datapoints.forEach((dp: DataPoint) => {
        max = Math.max(max, dp[1]);
    });
    return max;
}

export function smoothDataPoints(data: DataPoint[][]): DataPoint[][] {
    return data.map(xs => {
        xs = winsorizeDataPoints(xs);
        xs = medianFilter(xs, 15);
        xs = kernelSmooth(xs, 200);
        return xs;
    });
}

export function normalizeDataPoints(data: DataPoint[][]): DataPoint[][] {
    data.forEach((xs: DataPoint[]) => {
        let min: number = dpMin(xs), max: number = dpMax(xs);
        // normalization: z_i = (x_i – min(x)) / (max(x) – min(x))
        let delta = max - min;
        xs.forEach((value, index) => {
            let x: DataPoint = value;
            x[1] = +((x[1] - min) / delta);
            xs[index] = x;
        });
    });
    return data;
}