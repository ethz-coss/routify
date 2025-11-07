package ch.routify.routing.operations;

import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.OptionalDouble;
import java.util.Set;

import ch.routify.graph.CustomEdge;
import net.minidev.json.JSONObject;

/**
 * Shared state passed to each weight operation during pipeline execution.
 */
public class WeightOperationContext {

    private final Set<CustomEdge> edges;
    private final HashMap<CustomEdge, Double> baseWeights;
    private final JSONObject requestData;
    private final String routingMode;
    private final String transportMode;
    private final String[] allowedFeatures;
    private final HashSet<String> allowedFeatureSet;
    private double[] cachedNoiseBounds;

    public WeightOperationContext(Set<CustomEdge> edges,
                                  HashMap<CustomEdge, Double> baseWeights,
                                  JSONObject requestData,
                                  String routingMode,
                                  String transportMode,
                                  String[] allowedFeatures) {
        this.edges = edges;
        this.baseWeights = baseWeights;
        this.requestData = requestData;
        this.routingMode = routingMode;
        this.transportMode = transportMode;
        this.allowedFeatures = allowedFeatures;
        this.allowedFeatureSet = allowedFeatures == null ? null : new HashSet<>(Arrays.asList(allowedFeatures));
    }

    public Set<CustomEdge> getEdges() {
        return edges;
    }

    public HashMap<CustomEdge, Double> getBaseWeights() {
        return baseWeights;
    }

    public JSONObject getRequestData() {
        return requestData;
    }

    public String getRoutingMode() {
        return routingMode;
    }

    public String getTransportMode() {
        return transportMode;
    }

    public String[] getAllowedFeatures() {
        return allowedFeatures;
    }

    public HashSet<String> getAllowedFeatureSet() {
        return allowedFeatureSet;
    }

    public double[] getCachedNoiseBounds() {
        return cachedNoiseBounds;
    }

    public void setCachedNoiseBounds(double[] cachedNoiseBounds) {
        this.cachedNoiseBounds = cachedNoiseBounds;
    }

    public double requireDouble(String key) {
        Object raw = requestData == null ? null : requestData.get(key);
        if (raw == null) {
            throw new IllegalArgumentException(
                String.format("Missing request parameter '%s' for routing mode '%s'", key, routingMode));
        }
        return Double.parseDouble(raw.toString());
    }

    public double getDoubleOrDefault(String key, double defaultValue) {
        Object raw = requestData == null ? null : requestData.get(key);
        if (raw == null) {
            return defaultValue;
        }
        return Double.parseDouble(raw.toString());
    }

    public OptionalDouble getDouble(String key) {
        Object raw = requestData == null ? null : requestData.get(key);
        if (raw == null) {
            return OptionalDouble.empty();
        }
        return OptionalDouble.of(Double.parseDouble(raw.toString()));
    }
}
