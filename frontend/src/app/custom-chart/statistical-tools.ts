import { DataPoint } from "./data-point.model";

function gaussianKernel(distance: number, sigma: number): number {
  return Math.exp(-0.5 * (distance / sigma) ** 2);
}

export function kernelSmooth(data: DataPoint[], sigma: number): DataPoint[] {
  return data.map((point, _, array) => {
    let weightSum = 0;
    let weightedYSum = 0;

    array.forEach((otherPoint) => {
      const weight = gaussianKernel(Math.abs(point[0] - otherPoint[0]), sigma);
      weightedYSum += weight * otherPoint[1];
      weightSum += weight;
    });

    const smoothedY = weightedYSum / weightSum;
    return [point[0], smoothedY, point[2], point[3]]; // Keep x, lat, lon unchanged
  });
}

export function winsorizeDataPoints(data: DataPoint[]): DataPoint[] {
  // Extract y values
  const yValues = data.map(point => point[1]);

  // Calculate the 5th and 95th percentiles
  const lowerPercentile = percentile(yValues, 5);
  const upperPercentile = percentile(yValues, 95);

  // Apply Winsorization
  return data.map(point => {
    const winsorizedY = Math.min(Math.max(point[1], lowerPercentile), upperPercentile);
    return [point[0], winsorizedY, point[2], point[3]];
  });
}

// Helper function to calculate the nth percentile of an array
function percentile(arr: number[], p: number): number {
  const sorted = arr.slice().sort((a, b) => a - b);
  const index = (p / 100) * (sorted.length - 1);
  const lower = Math.floor(index);
  const upper = lower + 1;
  const weight = index % 1;
  
  if (upper >= sorted.length) return sorted[lower];
  return sorted[lower] * (1 - weight) + sorted[upper] * weight;
}

export function medianFilter(data: DataPoint[], windowSize: number): DataPoint[] {
  if (windowSize % 2 === 0) {
    throw new Error('Window size must be odd.');
  }
  
  // Function to calculate the median of an array of numbers
  const median = (arr: number[]) => {
    const mid = Math.floor(arr.length / 2);
    const nums = [...arr].sort((a, b) => a - b);
    return arr.length % 2 !== 0 ? nums[mid] : (nums[mid - 1] + nums[mid]) / 2;
  };

  return data.map((_, index, arr) => {
    // Start and end indices for the slice, ensuring we don't go out of bounds
    const start = Math.max(0, index - Math.floor(windowSize / 2));
    const end = Math.min(arr.length, index + Math.floor(windowSize / 2) + 1);
    
    // Slice the array to get the window and then calculate the median of the window
    const window = arr.slice(start, end).map(point => point[1]);
    const medianY = median(window);
    
    // Clone the data point and replace the y value with the median
    const dataPoint = [...arr[index]];
    dataPoint[1] = medianY;
    
    return dataPoint as DataPoint;
  });
}
