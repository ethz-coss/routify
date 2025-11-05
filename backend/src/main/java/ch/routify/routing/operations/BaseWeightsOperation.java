package ch.routify.routing.operations;

import java.util.HashMap;

import ch.routify.graph.CustomEdge;

/**
 * Initializes the pipeline with a fresh copy of the precomputed base weights.
 */
public class BaseWeightsOperation implements WeightOperation {

    @Override
    public HashMap<CustomEdge, Double> apply(WeightOperationContext context, HashMap<CustomEdge, Double> current) {
        return new HashMap<>(context.getBaseWeights());
    }
}
