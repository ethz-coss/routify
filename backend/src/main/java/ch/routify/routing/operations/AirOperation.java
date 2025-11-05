package ch.routify.routing.operations;

import java.util.HashMap;
import java.util.Map;

import ch.routify.graph.CustomEdge;

/**
 * Penalises edges with higher PM10 values based on processed air quality data.
 */
public class AirOperation implements WeightOperation {

    private final String impactField;
    private final double alpha;

    public AirOperation(Map<String, Object> params) {
        this.impactField = params != null && params.containsKey("impactField")
            ? params.get("impactField").toString()
            : "air";
        this.alpha = params != null && params.containsKey("alpha")
            ? Double.parseDouble(params.get("alpha").toString())
            : 20.0;
    }

    @Override
    public HashMap<CustomEdge, Double> apply(WeightOperationContext context, HashMap<CustomEdge, Double> current) {
        if (current == null) {
            throw new IllegalStateException("AirOperation requires base weights to run first");
        }

        // Preserve parameter usage semantics from previous implementation.
        context.requireDouble(impactField);

        HashMap<CustomEdge, Double> updated = new HashMap<>(current.size());
        for (Map.Entry<CustomEdge, Double> entry : current.entrySet()) {
            CustomEdge edge = entry.getKey();
            double distance = edge.getDistance();
            double weight = entry.getValue();

            if (edge.getPm_10() >= 0) {
                double exponent = Math.exp(edge.getPm_10() - CustomEdge.minPm10);
                weight = weight + alpha * exponent;
            } else {
                weight = Double.POSITIVE_INFINITY;
            }
            updated.put(edge, weight);
        }
        return updated;
    }
}
