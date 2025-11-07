package ch.routify.routing.operations;

import static ch.routify.routing.operations.NormalizationUtils.clamp;
import static ch.routify.routing.operations.NormalizationUtils.normalizeImpact;

import java.util.HashMap;
import java.util.Map;

import ch.routify.graph.CustomEdge;

/**
 * Adjusts weights to favour edges with higher green index. The slider value from
 * the request is interpreted as a percentage (0–100) and normalized to [0, 1],
 * while the green index provided by the graph is already in [0, 1] but is
 * clamped defensively.
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

        double impact = normalizeImpact(context.requireDouble(impactField));
        HashMap<CustomEdge, Double> updated = new HashMap<>(current.size());
        for (Map.Entry<CustomEdge, Double> entry : current.entrySet()) {
            CustomEdge edge = entry.getKey();
            double weight = entry.getValue();

            if (edge.getGreenIndex() >= 0 && edge.getGreenIndex() <= 1.0) {
                double normalizedGreen = clamp(edge.getGreenIndex(), 0.0, 1.0);
                double penalty = (1.0 - normalizedGreen) * impact * accelerate;
                weight = weight * (1.0 + penalty);
            } else {
                weight = Double.POSITIVE_INFINITY;
            }
            updated.put(edge, weight);
        }
        return updated;
    }
}
