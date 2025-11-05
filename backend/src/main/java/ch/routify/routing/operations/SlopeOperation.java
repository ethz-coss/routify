package ch.routify.routing.operations;

import java.util.HashMap;
import java.util.Map;

import ch.routify.graph.CustomEdge;

/**
 * Penalises edges whose slope exceeds the requested limit.
 */
public class SlopeOperation implements WeightOperation {

    private final String thresholdField;
    private final double penaltyMultiplier;

    public SlopeOperation(Map<String, Object> params) {
        this.thresholdField = params != null && params.containsKey("thresholdField")
            ? params.get("thresholdField").toString()
            : "slope";
        this.penaltyMultiplier = params != null && params.containsKey("penaltyMultiplier")
            ? Double.parseDouble(params.get("penaltyMultiplier").toString())
            : 20.0;
    }

    @Override
    public HashMap<CustomEdge, Double> apply(WeightOperationContext context, HashMap<CustomEdge, Double> current) {
        if (current == null) {
            throw new IllegalStateException("SlopeOperation requires base weights to run first");
        }

        double limit = context.requireDouble(thresholdField) / 100.0;
        HashMap<CustomEdge, Double> updated = new HashMap<>(current.size());
        for (Map.Entry<CustomEdge, Double> entry : current.entrySet()) {
            CustomEdge edge = entry.getKey();
            double weight = entry.getValue();
            try {
                double slope = Math.abs(edge.getSlope());
                if (edge.getSlope() > limit) {
                    weight += penaltyMultiplier * edge.getDistance() * (1 + slope);
                }
            } catch (Exception exception) {
                weight = Double.POSITIVE_INFINITY;
            }
            updated.put(edge, weight);
        }
        return updated;
    }
}
