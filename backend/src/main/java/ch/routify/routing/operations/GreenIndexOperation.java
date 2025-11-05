package ch.routify.routing.operations;

import java.util.HashMap;
import java.util.Map;

import ch.routify.graph.CustomEdge;

/**
 * Adjusts weights to favour edges with higher green index.
 */
public class GreenIndexOperation implements WeightOperation {

    private final String impactField;
    private final double accelerate;

    public GreenIndexOperation(Map<String, Object> params) {
        this.impactField = params != null && params.containsKey("impactField")
            ? params.get("impactField").toString()
            : "green_index";
        this.accelerate = params != null && params.containsKey("accelerate")
            ? Double.parseDouble(params.get("accelerate").toString())
            : 2.0;
    }

    @Override
    public HashMap<CustomEdge, Double> apply(WeightOperationContext context, HashMap<CustomEdge, Double> current) {
        if (current == null) {
            throw new IllegalStateException("GreenIndexOperation requires base weights to run first");
        }

        double impact = context.requireDouble(impactField);
        HashMap<CustomEdge, Double> updated = new HashMap<>(current.size());
        for (Map.Entry<CustomEdge, Double> entry : current.entrySet()) {
            CustomEdge edge = entry.getKey();
            double weight = entry.getValue();

            if (edge.getGreenIndex() >= 0 && edge.getGreenIndex() <= 1.0) {
                weight = current.get(edge) + edge.getDistance() * impact * accelerate * (1 - edge.getGreenIndex());
            } else {
                weight = Double.POSITIVE_INFINITY;
            }
            updated.put(edge, weight);
        }
        return updated;
    }
}
