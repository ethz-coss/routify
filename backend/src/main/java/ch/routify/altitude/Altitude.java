package ch.routify.altitude;

import java.io.BufferedReader;
import java.io.FileWriter;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.HashSet;

import ch.routify.Routify;

import ch.routify.osmparser.OsmParser;
import geotrellis.proj4.CRS;
import geotrellis.proj4.Transform;
import net.minidev.json.JSONArray;
import net.minidev.json.JSONObject;
import net.minidev.json.JSONValue;
import scala.Tuple2;

/**
 * The Altitude class provides functionality to convert geographical coordinates
 * between different coordinate reference systems (CRS), make HTTP requests to an API
 * for altitude data, and export this data to a JSON file.
 * 
 * <p>This is a utility class for generating altitude data from external APIs.
 * It can be adapted for different coordinate systems and altitude services.
 * 
 * @author Alexander Eggerth
 * @since 2025-02-05 (Updated for tolerance-based comparison by Sachit Mahajan)
 * @version 1.0
 */
class Altitude {

    /** EPSG:4326 WGS 84 coordinate reference system. */
    public static CRS wgs84 = CRS.fromEpsgCode(4326);
    /** EPSG:2056 coordinate reference system (example: CH1903+ / LV95). */
    public static CRS epsg2056 = CRS.fromEpsgCode(2056);
    /** EPSG:21781 coordinate reference system (example: CH1903 / LV03). */
    public static CRS epsg21781 = CRS.fromEpsgCode(21781);

	/**
     * Main method to demonstrate the usage of Altitude.
     * 
     * @param args Command line arguments (not used).
     * @throws Exception if initialization or export fails.
     */
    public static void main(String[] args) throws Exception {
        // Example usage - replace with your actual file paths
        export("path/to/your/basemap.json",
            "path/to/your/output/altitude_data.json");
	}

    /**
     * Converts geographical coordinates from WGS 84 to a target coordinate system.
     * 
     * @param data Array containing latitude and longitude in WGS 84.
     * @return Array containing converted coordinates in the target CRS.
     */
    public static double[] convertToEpsg2056(double[] data) {
        var wgs84ToEpsg2056 = Transform.apply(wgs84, epsg2056);
        Tuple2<Object, Object> cEpsg2056 = wgs84ToEpsg2056.apply(data[1], data[0]);
        return new double[] {(double) cEpsg2056._1(), (double) cEpsg2056._2()};
    }

    /**
     * Sends a request to an API to retrieve altitude data for a list of coordinates.
     * 
     * @param coordinates JSONArray of coordinate pairs to request altitude data for.
     * @param amount The number of points to request data for.
     * @return JSONArray containing the altitude data response from the API.
     * @throws Exception if the request fails.
     */
    public static JSONArray request(JSONArray coordinates, int amount) throws Exception {
        JSONObject geom = new JSONObject();
        geom.appendField("type", "LineString");
        geom.appendField("coordinates", coordinates);

        // Example API endpoint - replace with your actual altitude service URL
        String requestString = "https://your-altitude-api.com/rest/services/profile.json?geom=" + geom.toJSONString() + "&sr=2056&distinct_points=true&nb_points=" + amount;
        
        String requestResponse = callRequest(requestString);

        JSONArray responseData = (JSONArray) JSONValue.parse(requestResponse);
        return responseData;
    }

    /**
     * Exports altitude data obtained from API to a JSON file.
     * 
     * @throws Exception if the export process fails.
     */
    public static void export(String inputPath, String outputPath) throws Exception {
        
        OsmParser parser = new OsmParser(inputPath);
        JSONArray nodes = parser.getNodes();

        // we need to write the file in batches because FileWriter cannot handle filesizes like output at admin_level_4
        try (FileWriter file = new FileWriter(outputPath)) {
            file.write("{\n");
            
            // batchsize defines the amount of nodes that are queried by on request
            int batchSize = 80; // max 5000

            // contains coordinates converted to lineString ins OSM convention [lat, lon] as double[]
            JSONArray lineStrings = new JSONArray();

            // loop over nodes to populate lineStrings and OsmIds
            for(Object o : nodes) {
                JSONObject node = (JSONObject) o;
                double[] lineString = {(double) node.get("lat"), (double) node.get("lon")};
                // convert coordinate format to target CRS (example: EPSG2056 for Swiss coordinate system)
                lineStrings.add(convertToEpsg2056(lineString));
            }

            // keep track of exported osmIds to avoid duplicate entries
            HashSet<Long> osmids = new HashSet<>();

            int size = lineStrings.size();
            // indexvariable for loop unrolling
            int i;
            for (i = 0; i < size - batchSize; i += batchSize) {

                JSONArray subarray = getSubArray(lineStrings, i, i + batchSize);
                JSONArray responseData = request(subarray, subarray.size());

                // subarray of nodes
                JSONArray subarrayNodes = getSubArray(nodes, i, i + batchSize);
                writeToFile(responseData, subarrayNodes, osmids, i, file, size);

                Routify.logger.debug("Requested altitude data: {}/{}", i + batchSize, size);
            }

            // request last batch
            JSONArray subarray = getSubArray(lineStrings, i, size - 1);
            JSONArray subarrayNodes = getSubArray(nodes, i, size- 1);
            JSONArray responseData = request(subarray, subarray.size());

            writeToFile(responseData, subarrayNodes, osmids, i, file, size);

            file.write("\n}");
            file.flush();
            Routify.logger.info("Finished requesting altitude data from external API");
        } catch (Exception e) {
            Routify.logger.error("Error requesting altitude data", e);
        }
    }

    /**
     * Writes altitude data to a file for matching geographical coordinates between response data and OSM node data.
     * 
     * @param responseData JSONArray of response data with elevation and coordinates.
     * @param subarrayNodes JSONArray of OSM node data with latitudes, longitudes, and IDs.
     * @param osmids Set of OSM IDs to avoid duplicates in the output.
     * @param i Index in processing loop for output formatting.
     * @param file FileWriter to write output.
     * @param size Total number of elements for output formatting.
     * @throws IOException If writing to the file fails.
     */
    private static void writeToFile(JSONArray responseData, JSONArray subarrayNodes, HashSet<Long> osmids, int i, FileWriter file, int size) throws IOException {
        var epsg2056ToWgs84 = Transform.apply(epsg2056, wgs84);
        // A flag to manage comma placement in the output.
        boolean isFirstInFile = (i == 0);

        // CHANGED: Define a tolerance (epsilon) for comparing coordinates instead of rounding.
        final double epsilon = 1e-6;
        
        int responseSize = responseData.size();
        for (int j = 0; j < responseSize; j++) {
            JSONObject json = (JSONObject) responseData.get(j);

            // Structure of json:
            // {
            //     "alts": {
            //         "COMB": 833.1,
            //         "DTM2": 833.1,
            //         "DTM25": 833.1
            //     },
            //     "dist": 8487.0,
            //     "easting": 2679523.792,
            //     "northing": 1244786.535
            // }

            double easting = (double) json.get("easting");
            double northing = (double) json.get("northing");
            Tuple2<Object, Object> cordWgs84 = epsg2056ToWgs84.apply(easting, northing);
            double lat = (double) cordWgs84._2();
            double lon = (double) cordWgs84._1();
            
            // Extract altitude value (using DTM2 as the preferred value - adjust based on your API response format)
            double alt = (double) ((JSONObject) json.get("alts")).get("DTM2");

            // CHANGED: Use a tolerance-based comparison to match coordinates.
            for (Object o : subarrayNodes) {
                JSONObject node = (JSONObject) o;
                double nodeLat = (double) node.get("lat");
                double nodeLon = (double) node.get("lon");
                
                if (Math.abs(nodeLat - lat) < epsilon && Math.abs(nodeLon - lon) < epsilon) {
                    // Found matching response entry; check for duplicate
                    Long osmId = (Long) node.get("id");
                    if (!osmids.contains(osmId)) {
                        String prefix = isFirstInFile ? "" : ",\n";
                        file.write(String.format("%s\t\"%d\" : %f", prefix, osmId, alt));
                        isFirstInFile = false;
                    }
                    osmids.add(osmId);
                }
            }
        }
    }

    /**
     * Returns a new JSONArray containing a subset of elements from the specified range of the original array.
     * 
     * @param basearray The original JSONArray.
     * @param start The starting index, inclusive, from which to begin extraction.
     * @param end The ending index, exclusive, to end the extraction.
     * @return A JSONArray containing elements from the start index up to, but not including, the end index.
     */
    private static JSONArray getSubArray(JSONArray basearray, int start, int end) {
        JSONArray subarray = new JSONArray();
        for (int i = start; i < end; i++) {
            subarray.add(basearray.get(i));
        }
        return subarray;
    }

    /**
     * Performs an HTTP GET request to the specified URL.
     * 
     * @param requestString The URL to send the request to.
     * @return A string containing the response from the request.
     * @throws Exception if the request fails.
     */
    protected static String callRequest(String requestString) throws Exception {
        StringBuilder result = new StringBuilder();
        URL url = new URL(requestString);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod("GET");
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()))) {
            for (String line; (line = reader.readLine()) != null; ) {
                result.append(line);
            }
        }
        return result.toString();
    }

    // Method to get the number of decimal places of a double
    public static int getDecimalPlaces(double value) {
        String text = Double.toString(Math.abs(value));
        int integerPlaces = text.indexOf('.');
        if (integerPlaces == -1) {
            // No decimal places
            return 0;
        }
        // Subtract the number of digits up to and including the decimal point
        return text.length() - integerPlaces - 1;
    }

    // Method to round a double to a specified number of decimal places
    public static double roundToDecimalPlaces(double value, int decimalPlaces) {
        double scale = Math.pow(10, decimalPlaces);
        return Math.round(value * scale) / scale;
    }

    // public static void testRounding() {
    //     double originalValue = 47.348627;
    //     double valueToRound = 47.34862701436589;

    //     // Get the precision of the original value
    //     int decimalPlaces = getDecimalPlaces(originalValue);

    //     // Round another value to the same precision
    //     double roundedValue = roundToDecimalPlaces(valueToRound, decimalPlaces);

    // }

}
