package ch.routify.routing.operations;

import static ch.routify.routing.operations.NormalizationUtils.normalize;
import static ch.routify.routing.operations.NormalizationUtils.normalizeImpact;

import java.util.HashMap;
import java.util.Map;

import ch.routify.graph.CustomEdge;

/**
 * Penalises edges with higher PM10 values based on processed air quality data.
 * Both the slider value (impact) and the PM10 measurements are normalized to
 * [0, 1] so that small differences remain visible while keeping the resulting
 * factor stable across datasets.
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

        double impact = normalizeImpact(context.requireDouble(impactField));

        HashMap<CustomEdge, Double> updated = new HashMap<>(current.size());
        for (Map.Entry<CustomEdge, Double> entry : current.entrySet()) {
            CustomEdge edge = entry.getKey();
            double weight = entry.getValue();

            if (edge.getPm_10() >= 0) {
                double normalized = normalize(edge.getPm_10(), CustomEdge.minPm10, CustomEdge.maxPm10);
                double factor = 1.0 + normalized * impact * alpha;
                weight = weight * factor;
            } else {
                weight = Double.POSITIVE_INFINITY;
            }
            updated.put(edge, weight);
        }
        return updated;
    }
}
