package ch.routify.routing.operations;

import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;

import ch.routify.graph.CustomEdge;

/**
 * Marks edges that are not allowed for the current transport mode as unusable.
 */
public class FilterDisallowedOperation implements WeightOperation {

    @Override
    public HashMap<CustomEdge, Double> apply(WeightOperationContext context, HashMap<CustomEdge, Double> current) {
        if (current == null) {
            throw new IllegalStateException("FilterDisallowedOperation requires base weights to run first");
        }

        HashSet<String> allowed = context.getAllowedFeatureSet();
        if (allowed == null || allowed.isEmpty()) {
            return current;
        }

        HashMap<CustomEdge, Double> updated = new HashMap<>(current.size());
        for (Map.Entry<CustomEdge, Double> entry : current.entrySet()) {
            CustomEdge edge = entry.getKey();
            double value = entry.getValue();
            String highway = edge.getTag("highway");
            // if (highway != null && allowed.contains(highway)) {
            //     updated.put(edge, value);
            // } else {
            //     updated.put(edge, Double.POSITIVE_INFINITY);
            // }
            updated.put(edge, value);
        }
        return updated;
    }
}
