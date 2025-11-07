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
    private static final double EPSILON = 1e-6;

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

        double impact = context.requireDouble(impactField);

        HashMap<CustomEdge, Double> updated = new HashMap<>(current.size());
        for (Map.Entry<CustomEdge, Double> entry : current.entrySet()) {
            CustomEdge edge = entry.getKey();
            double weight = entry.getValue();

            if (edge.getPm_10() >= 0) {
                double normalized = normalizePm10(edge.getPm_10());
                double factor = 1.0 + normalized * impact * alpha;
                weight = weight * factor;
            } else {
                weight = Double.POSITIVE_INFINITY;
            }
            updated.put(edge, weight);
        }
        return updated;
    }

    private double normalizePm10(double value) {
        double min = CustomEdge.minPm10;
        double max = CustomEdge.maxPm10;
        if (value < min) {
            return 0.0;
        }
        if (value > max) {
            return 1.0;
        }

        double range = Math.max(EPSILON, max - min);
        return (value - min) / range;
    }
}
