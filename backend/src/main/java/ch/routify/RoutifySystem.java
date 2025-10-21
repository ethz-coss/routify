package ch.routify;

import java.io.BufferedReader;
import java.io.FileNotFoundException;
import java.io.FileReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.URL;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Set;

import org.apache.http.HttpEntity;
import org.apache.http.client.methods.CloseableHttpResponse;
import org.apache.http.client.methods.HttpPost;
import org.apache.http.entity.StringEntity;
import org.apache.http.impl.client.CloseableHttpClient;
import org.apache.http.impl.client.HttpClients;
import org.apache.http.util.EntityUtils;
import org.springframework.stereotype.Component;
import org.slf4j.LoggerFactory;
import org.springframework.boot.json.JsonParseException;
import org.springframework.scheduling.annotation.Scheduled;

import ch.routify.graph.CustomVertex;
import ch.routify.osmparser.OsmParser;
import ch.qos.logback.classic.Level;
import ch.qos.logback.classic.Logger;
import ch.routify.graph.CustomEdge;
import ch.routify.graph.CustomGraph;
import net.minidev.json.JSONArray;
import net.minidev.json.JSONObject;
import net.minidev.json.parser.JSONParser;
import net.minidev.json.parser.ParseException;

/**
 * Initializes graph and metadata using local resource files only.
 */
@Component
public class RoutifySystem {

    static {
        Logger logger = (Logger) LoggerFactory.getLogger("org.apache.http.wire");
        logger.setLevel(Level.WARN);
        Logger loggerHeaders = (Logger) LoggerFactory.getLogger("org.apache.http.headers");
        loggerHeaders.setLevel(Level.WARN);
        Logger loggerMainClientExec = (Logger) LoggerFactory.getLogger("org.apache.http.impl.execchain.MainClientExec");
        loggerMainClientExec.setLevel(Level.WARN);
        Logger loggerPoolingConn = (Logger) LoggerFactory.getLogger("org.apache.http.impl.conn.PoolingHttpClientConnectionManager");
        loggerPoolingConn.setLevel(Level.WARN);
        Logger loggerConnectionOp = (Logger) LoggerFactory.getLogger("org.apache.http.impl.conn.DefaultHttpClientConnectionOperator");
        loggerConnectionOp.setLevel(Level.WARN);
        Logger loggerManagedConn = (Logger) LoggerFactory.getLogger("org.apache.http.impl.conn.DefaultManagedHttpClientConnection");
        loggerManagedConn.setLevel(Level.WARN);
        Logger loggerAddCookies = (Logger) LoggerFactory.getLogger("org.apache.http.client.protocol.RequestAddCookies");
        loggerAddCookies.setLevel(Level.WARN);
        Logger loggerAuthCache = (Logger) LoggerFactory.getLogger("org.apache.http.client.protocol.RequestAuthCache");
        loggerAuthCache.setLevel(Level.WARN);
        Logger loggerConnSocket = (Logger) LoggerFactory.getLogger("org.apache.http.conn.ssl.SSLConnectionSocketFactory");
        loggerConnSocket.setLevel(Level.WARN);
    }

    private String path_to_map = new RoutifyConfig().getPathToMap();
    private String path_conf_features = new RoutifyConfig().getPathConfFeatures();
    private String path_altitude = new RoutifyConfig().getPathAltitude();
    private String path_green_index = new RoutifyConfig().getPathGreenIndex();
    private String path_noise = new RoutifyConfig().getPathNoise();
    private String path_to_boundary = new RoutifyConfig().getPathToBoundary();

    public JSONObject config_features;
    private JSONObject altitude_data;
    private JSONObject noise_data;
    private JSONObject green_index_data;

    private CustomGraph<CustomVertex, CustomEdge> graph = new CustomGraph<>(CustomEdge.class);
    private HashMap<String, HashMap<String, Double>> weight_modifiers = new HashMap<>();
    private HashMap<CustomEdge, Double> weightsWalk = new HashMap<>();
    private HashMap<CustomEdge, Double> weightsBike = new HashMap<>();
    private HashMap<CustomEdge, Double> weightsDrive = new HashMap<>();

    private final String[] allowedFeaturesWalk = new RoutifyConfig().getAllowedFeaturesWalk();
    private final String[] allowedFeaturesBike = new RoutifyConfig().getAllowedFeaturesBike();
    private final String[] allowedFeaturesDrive = new RoutifyConfig().getAllowedFeaturesDrive();

    public void initialize() throws Exception {
        path_to_boundary = extendedPath(this.path_to_boundary);
        path_to_map = extendedPath(this.path_to_map);
        path_conf_features = extendedPath(this.path_conf_features);
        path_altitude = extendedPath(this.path_altitude);
        path_green_index = extendedPath(this.path_green_index);
        path_noise = extendedPath(this.path_noise);

        try {
            parseMetaData();
            loadTypeSets();
            loadGraph(path_to_map);
            for(CustomEdge e : graph.edgeSet()) {
                if(e.getSlope() >= 1) e.correctAltitude();
            }
            loadPM10();
        } catch(Exception e) {
            Routify.logger.error("error while initializing system", e);
            System.exit(0);
        }
    }

    @Scheduled(fixedRate=3600000)
    private void loadPM10() throws IOException {
        JSONObject jsonVertex = new JSONObject();
        JSONArray jsonPayload = new JSONArray();
        int i = 0;
        for(CustomVertex v : graph.vertexSet()) {
            i++;
            jsonVertex = new JSONObject();
            jsonVertex.put("id", v.getId());
            jsonVertex.put("lat", v.getLat());
            jsonVertex.put("lon", v.getLon());
            jsonPayload.add(jsonVertex);
            if(i % 1000 == 0) {
                requestPM10values(jsonPayload);
                jsonPayload = new JSONArray();
            }
        }
        requestPM10values(jsonPayload);
        Routify.logger.info("PM10 values have been updated");
    }

    private void requestPM10values(JSONArray payload) throws IOException {
        try (CloseableHttpClient httpClient = HttpClients.createDefault()) {
            double avgPm10 = 0.0;
            int i = 0;
            HttpPost request = new HttpPost(Routify.url_airquality);
            StringEntity params = new StringEntity(payload.toString());
            request.addHeader("Content-Type", "application/json");
            request.setEntity(params);

            try (CloseableHttpResponse response = httpClient.execute(request)) {
                HttpEntity entity = response.getEntity();
                if (entity != null) {
                    String jsonString = EntityUtils.toString(entity, "UTF-8");
                    JSONParser parser = new JSONParser();
                    try {
                        JSONArray jsonArray = (JSONArray) parser.parse(jsonString);
                        for (Object item : jsonArray) {
                            JSONObject json = (JSONObject) item;
                            long nodeId = (long) json.get("id");
                            CustomVertex.getByNodeId(nodeId).setPm10((double) json.get("pm_10"));
                            double pm10 = (double) json.get("pm_10");
                            avgPm10 += pm10;
                            CustomEdge.maxPm10 = Math.max(CustomEdge.maxPm10, pm10);
                            CustomEdge.minPm10 = Math.min(CustomEdge.minPm10, pm10);
                            i++;
                        }
                    } catch (ParseException pe) {
                        Routify.logger.error("Failed to parse PM10 data", pe);
                    }
                }
            }
            CustomEdge.avgPm10 = avgPm10 / (double) i;
        } catch (Exception ex) {
            Routify.logger.error("Error loading PM10 data", ex);
        }
    }

    public static BufferedReader getReader(String path) throws FileNotFoundException {
        try {
            // 1) Try classpath under static/ using multiple resolvers
            java.io.InputStream in = null;
            ClassLoader cl = Thread.currentThread().getContextClassLoader();
            if (cl != null) {
                in = cl.getResourceAsStream("static/" + path);
                if (in == null) in = cl.getResourceAsStream("/static/" + path);
                if (in == null) in = cl.getResourceAsStream(path);
                if (in == null) in = cl.getResourceAsStream("/" + path);
            }
            if (in == null) {
                in = RoutifySystem.class.getResourceAsStream("/static/" + path);
                if (in == null) in = RoutifySystem.class.getResourceAsStream("/" + path);
            }
            if (in != null) {
                return new BufferedReader(new InputStreamReader(in));
            }

            // 2) If an absolute/URL path was provided, support those too
            if (path.startsWith("http://") || path.startsWith("https://")) {
                URL url = new URL(path);
                return new BufferedReader(new InputStreamReader(url.openStream()));
            }

            // 3) Fallback to filesystem path
            return new BufferedReader(new FileReader(path));
        } catch (Exception e) {
            throw new FileNotFoundException(String.format("Ressource \"%s\" could not be found.", path));
        }
    }

    private void parseMetaData() throws Exception {
        config_features = (JSONObject) new JSONParser(JSONParser.MODE_JSON_SIMPLE).parse(getReader(path_conf_features));
        altitude_data = (JSONObject) new JSONParser(JSONParser.MODE_JSON_SIMPLE).parse(getReader(path_altitude));
        noise_data = (JSONObject) new JSONParser(JSONParser.MODE_JSON_SIMPLE).parse(getReader(path_noise));
        green_index_data = (JSONObject) new JSONParser(JSONParser.MODE_JSON_SIMPLE).parse(getReader(path_green_index));
    }

    public static String extendedPath(String filename) throws IOException {
        // Always use classpath resources; return the logical filename only
        return filename;
    }

    public JSONObject getAltData() { return altitude_data; }
    public JSONObject getNoiseData() { return noise_data; }
    public JSONObject getGreenIndexData() { return green_index_data; }
    public HashMap<String, HashMap<String, Double>> getWeightModifiers() { return weight_modifiers; }
    public CustomGraph<CustomVertex, CustomEdge> getGraph() { return graph; }
    public HashMap<CustomEdge, Double> getWeightsWalk() { return weightsWalk; }
    public HashMap<CustomEdge, Double> getWeightsBike() { return weightsBike; }
    public HashMap<CustomEdge, Double> getWeightsDrive() { return weightsDrive; }

    public JSONObject getBoundary() throws FileNotFoundException, ParseException {
        return (JSONObject) new JSONParser(JSONParser.MODE_JSON_SIMPLE).parse(getReader(path_to_boundary));
    }

    private void loadTypeSets() {
        String[] r_keys = {"walk", "bike", "drive"};
        try {
            Set<String> keys = config_features.keySet();
            for(String key : keys) {
                JSONObject type = (JSONObject) config_features.get(key);
                JSONObject modifiers = (JSONObject) type.get("weight_modifiers");
                HashMap<String, Double> mapModifiers = new HashMap<String, Double>();
                for(int i = 0; i < r_keys.length; i++) {
                    if(modifiers.containsKey(r_keys[i])) {
                        mapModifiers.put(r_keys[i], (Double) modifiers.get(r_keys[i]));
                    } else {
                        mapModifiers.put(r_keys[i], Double.MAX_VALUE);
                    }
                }
                weight_modifiers.put(key, mapModifiers);
            }
        } catch (Exception e) {
            Routify.logger.error("Error loading weight modifiers", e);
            throw new JsonParseException();
        }
    }

    private void loadGraph(String path) throws Exception {
        OsmParser bmp = new OsmParser(path);
        bmp.initializeGraph(graph);
        bmp.clear();
        graph.prune();
        Routify.logger.info(String.format("Graph has been initialized #vertices=%d, #edges=%d", graph.vertexSet().size(), graph.edgeSet().size()));
        if(Routify.devMode()) graph.exportGexf();
        setWeights("walk", weightsWalk, graph, allowedFeaturesWalk);
        setWeights("bike", weightsBike, graph, allowedFeaturesBike);
        setWeights("drive", weightsDrive, graph, allowedFeaturesDrive);
        Routify.logger.info("weights have been preloaded");
    }

    private void setWeights(String type, HashMap<CustomEdge, Double> targetWeights, CustomGraph<CustomVertex, CustomEdge> graph, String[] features) {
        HashSet<String> featuresSet = new HashSet<String>(Arrays.asList(features));
        for(CustomEdge edge : graph.edgeSet()) {
            double weight = edge.getDistance();
            String highway = edge.getTag("highway");
            if(featuresSet.contains(highway)) {
                if(weight_modifiers.keySet().contains(highway) && weight_modifiers.get(highway).keySet().contains(type)) {
                    weight *= (double) weight_modifiers.get(highway).get(type);
                } else {
                    Routify.logger.error(String.format("unknown_edge_type: %s", highway));
                    weight *= 10000;
                }
            } else {
                weight *= 10000;
            }
            targetWeights.put(edge, weight);
        }
    }

    public void fetchMetaData() throws Exception {
        parseMetaData();
        for(CustomVertex c : graph.vertexSet()) {
            c.loadMetaData();
        }
        for(CustomEdge e : graph.edgeSet()) {
            e.loadMetaData();
        }
    }
}


