package ch.routify.routing.config;

import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import ch.routify.graph.CustomEdge;
import ch.routify.routing.operations.WeightOperation;
import ch.routify.routing.operations.WeightOperationContext;
import ch.routify.routing.operations.WeightOperationFactory;
import net.minidev.json.JSONArray;
import net.minidev.json.JSONObject;
import net.minidev.json.parser.JSONParser;

/**
 * Loads routing mode definitions from configuration and exposes helper methods
 * to build weight maps per request.
 */
public class RoutingModeService {

    private static final String DEFAULT_RESOURCE = "/routing-modes.json";

    private final Map<String, RoutingModeDefinition> registry;

    public RoutingModeService() {
        this(DEFAULT_RESOURCE);
    }

    public RoutingModeService(String resourcePath) {
        this.registry = load(resourcePath);
    }

    public boolean hasMode(String mode) {
        return registry.containsKey(mode);
    }

    public Set<String> getAvailableModes() {
        return Collections.unmodifiableSet(registry.keySet());
    }

    public HashMap<CustomEdge, Double> computeWeights(String mode,
                                                      String transportMode,
                                                      JSONObject requestData,
                                                      Set<CustomEdge> edges,
                                                      HashMap<CustomEdge, Double> baseWeights,
                                                      String[] allowedFeatures) {
        RoutingModeDefinition definition = registry.get(mode);
        if (definition == null) {
            throw new IllegalArgumentException("Unknown routing mode: " + mode);
        }

        WeightOperationContext context = new WeightOperationContext(
            edges, baseWeights, requestData, mode, transportMode, allowedFeatures);

        HashMap<CustomEdge, Double> current = null;
        for (WeightOperation operation : definition.getOperations()) {
            current = operation.apply(context, current);
        }

        if (current == null) {
            throw new IllegalStateException("Routing mode '" + mode + "' did not produce weights");
        }

        return current;
    }

    private Map<String, RoutingModeDefinition> load(String resourcePath) {
        Map<String, RoutingModeDefinition> result = new HashMap<>();
        try (InputStream stream = RoutingModeService.class.getResourceAsStream(resourcePath)) {
            if (stream == null) {
                throw new IllegalStateException("Unable to find routing mode configuration: " + resourcePath);
            }

            JSONParser parser = new JSONParser(JSONParser.MODE_JSON_SIMPLE);
            JSONObject root = (JSONObject) parser.parse(new InputStreamReader(stream, StandardCharsets.UTF_8));

            for (Object keyObj : root.keySet()) {
                String modeName = keyObj.toString();
                JSONArray operationsArray = (JSONArray) root.get(modeName);
                List<WeightOperation> operations = new ArrayList<>();

                for (Object entry : operationsArray) {
                    JSONObject opJson = (JSONObject) entry;
                    String identifier = opJson.getAsString("operation");
                    JSONObject params = (JSONObject) opJson.get("params");
                    Map<String, Object> paramMap = params == null ? null : params;

                    operations.add(WeightOperationFactory.create(identifier, paramMap));
                }

                result.put(modeName, new RoutingModeDefinition(modeName, Collections.unmodifiableList(operations)));
            }
        } catch (Exception e) {
            throw new IllegalStateException("Failed to load routing mode definitions", e);
        }
        return Collections.unmodifiableMap(result);
    }
}
