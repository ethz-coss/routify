package ch.routify.routing.operations;

import static ch.routify.routing.operations.NormalizationUtils.normalize;
import static ch.routify.routing.operations.NormalizationUtils.normalizeImpact;

import java.util.HashMap;
import java.util.Map;
import java.util.Set;

import ch.routify.graph.CustomEdge;

/**
 * Penalises edges according to their (normalized) noise level. Both the slider
 * value and the underlying noise data are converted to the [0, 1] range so that
 * penalties stay comparable across datasets.
 */
public class NoiseOperation implements WeightOperation {

    private final String impactField;
    private final double accelerate;

    public NoiseOperation(Map<String, Object> params) {
        this.impactField = params != null && params.containsKey("impactField")
            ? params.get("impactField").toString()
            : "noise";
        this.accelerate = params != null && params.containsKey("accelerate")
            ? Double.parseDouble(params.get("accelerate").toString())
            : 1.0;
    }

    @Override
    public HashMap<CustomEdge, Double> apply(WeightOperationContext context, HashMap<CustomEdge, Double> current) {
        if (current == null) {
            throw new IllegalStateException("NoiseOperation requires base weights to run first");
        }

        double impact = normalizeImpact(context.requireDouble(impactField));
        double[] noiseBounds = context.getCachedNoiseBounds();
        if (noiseBounds == null) {
            noiseBounds = computeNoiseBounds(context.getEdges());
            context.setCachedNoiseBounds(noiseBounds);
        }

        HashMap<CustomEdge, Double> updated = new HashMap<>(current.size());
        for (Map.Entry<CustomEdge, Double> entry : current.entrySet()) {
            CustomEdge edge = entry.getKey();
            double weight = entry.getValue();
            double noise = edge.getNoise();

            if (noise < 0 || noiseBounds == null) {
                updated.put(edge, Double.POSITIVE_INFINITY);
                continue;
            }

            double normalizedNoise = normalize(noise, noiseBounds[0], noiseBounds[1]);
            double factor = 1.0 + normalizedNoise * impact * accelerate;
            updated.put(edge, weight * factor);
        }
        return updated;
    }

    /**
     * Computes the min/max noise values present in the current graph so that
     * the penalties stay relative to the observed distribution.
     */
    private double[] computeNoiseBounds(Set<CustomEdge> edges) {
        double min = Double.POSITIVE_INFINITY;
        double max = Double.NEGATIVE_INFINITY;

        for (CustomEdge edge : edges) {
            double noise = edge.getNoise();
            if (noise < 0) {
                continue;
            }
            min = Math.min(min, noise);
            max = Math.max(max, noise);
        }

        if (min == Double.POSITIVE_INFINITY || max == Double.NEGATIVE_INFINITY) {
            return null;
        }
        return new double[] { min, max };
    }
}
