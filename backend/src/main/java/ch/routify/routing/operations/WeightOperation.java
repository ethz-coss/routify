package ch.routify.routing.operations;

import java.util.HashMap;

import ch.routify.graph.CustomEdge;

/**
 * Contract for all weight operations that can be composed to build routing weight pipelines.
 */
public interface WeightOperation {

    /**
     * Applies the operation to the current weight map and returns the updated weights.
     *
     * @param context shared input data for the pipeline execution
     * @param current current weight map (null for the first operation)
     * @return updated weights (never null)
     */
    HashMap<CustomEdge, Double> apply(WeightOperationContext context, HashMap<CustomEdge, Double> current);
}
