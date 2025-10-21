package ch.routify.revgeocode;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;

import ch.routify.Routify;
import ch.routify.graph.CustomVertex;
import net.minidev.json.JSONArray;
import net.minidev.json.JSONObject;
import net.minidev.json.parser.JSONParser;
import scala.Tuple2;

/**
 * The {@link RevGeoCode} class provides functionality to reverse geocode addresses
 * to geographic coordinates using the Photon GeoCoder.
 * It includes methods to convert an address string to a {@link CustomVertex} object
 * representing its geographic location (latitude and longitude).
 */
public class RevGeoCode {

    /**
     * Main method for testing the reverse geocoding functionality.
     * 
     * @param args Command line arguments (not used).
     * @throws Exception if there is an issue with the reverse geocoding process.
     */
    public static void main(String[] args) throws Exception {
        CustomVertex cOffice = getCoordinates("Stampfenbachstrasse 48, 8006 Zürich");
        Routify.logger.info("Test geocoding result: {}", cOffice.toString());
    }

    /**
     * Converts an address to a {@link CustomVertex} object representing its geographic
     * coordinates (latitude and longitude).
     * 
     * @param address The address to geocode.
     * @return A {@link CustomVertex} object with the geographic coordinates.
     * @throws Exception if the address cannot be resolved or if an error occurs during the process.
     */
    public static CustomVertex getCoordinates(String address) throws Exception {
        try {            
            // reverse geo code using local photon service
            String url = String.format("http://%s/api?q=%s&lat=47.382215169614895&lon=8.537124125464356", Routify.url_geocoder, URLEncoder.encode(address, "UTF-8"));
            String response = getHTML(url);
            JSONObject jsonData = (JSONObject) new JSONParser(JSONParser.MODE_JSON_SIMPLE).parse(response);
            JSONArray features = (JSONArray) jsonData.get("features");
            JSONObject feature = (JSONObject) features.get(0);
            JSONObject geometry = (JSONObject) feature.get("geometry");
            JSONArray coordinates = (JSONArray) geometry.get("coordinates");
            double lat = (double) coordinates.get(1);
            double lon = (double) coordinates.get(0);
            JSONObject properties = (JSONObject) feature.get("properties");
            return Routify.vertexFactory.createObject(lat, lon, (long) properties.get("osm_id"));
        } catch(Exception e) {
            Routify.logger.error("Failed to resolve address: {}", address, e);
            throw new Exception(String.format("could not resolve address: %s", address));
        }
    }

    /**
     * Resolves the request addresses to {@link CustomVertex} objects based on the input data.
     * 
     * @param data A {@link JSONObject} containing the request data.
     * @return A {@link Tuple2} containing the resolved start and end {@link CustomVertex}.
     * @throws Exception if the addresses cannot be resolved.
     */
    public static Tuple2<CustomVertex, CustomVertex> resolveRequestAddresses(JSONObject data) throws Exception {
        CustomVertex vFrom = null, vTo = null;

        // check if requested origin address needs to be resolved further        
        if(data.containsKey("fromLat") && data.containsKey("fromLon")) {
            vFrom = Routify.vertexFactory.createObject((double) data.get("fromLat"), (double) data.get("fromLon"), 0L);
        } else if(data.containsKey("from")) {
            vFrom = RevGeoCode.getCoordinates((String) data.get("from"));
        } else {
            throw new Exception("INVALID_REQUEST_STRUCTURE");
        }

        // check if requested destination address needs to be resolved further
        if(data.containsKey("toLat") && data.containsKey("toLon")) {
            vTo = Routify.vertexFactory.createObject((double) data.get("toLat"), (double) data.get("toLon"), 0L);
        } else if(data.containsKey("to")) {
            vTo = RevGeoCode.getCoordinates((String) data.get("to"));
        } else {
            throw new Exception("INVALID_REQUEST_STRUCTURE");
        }
        return new Tuple2<CustomVertex,CustomVertex>(vFrom, vTo);
    }

    /**
     * Makes an HTTP GET request to the specified URL and returns the response content as a string.
     * 
     * @param urlToRead The URL to send the GET request to.
     * @return The response content from the URL as a string.
     * @throws Exception if an error occurs during the HTTP request.
     */
    public static String getHTML(String urlToRead) throws Exception {
        StringBuilder result = new StringBuilder();
        URL url = new URL(urlToRead);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod("GET");
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()))) {
            for (String line; (line = reader.readLine()) != null; ) {
                result.append(line);
            }
        }
        return result.toString();
    }
}
