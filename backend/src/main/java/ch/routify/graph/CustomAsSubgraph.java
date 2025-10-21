package ch.routify.graph;

import java.util.Set;

import org.jgrapht.Graph;
import org.jgrapht.graph.AsSubgraph;

/**
 * Extends the functionality of AsSubgraph to provide specific operations for custom vertices.
 *
 * @param <V> the graph vertex type
 * @param <E> the graph edge type
 * 
 * @author aeggerth@ethz.ch
 * @version 1.0
 */
public class CustomAsSubgraph<V, E> extends AsSubgraph<V, E> {

    /**
     * Constructs a new CustomAsSubgraph with the specified base graph and set of vertices.
     *
     * @param baseGraph the base graph on which the subgraph will be based
     * @param vertices  the vertices to include in the subgraph
     */
    public CustomAsSubgraph(Graph<V, E> baseGraph, Set<V> vertices) {
        super(baseGraph, vertices);
    }

    /**
     * Searches for the vertex in the subgraph that is nearest to the specified vertex.
     *
     * @param vFrom the vertex from which to measure distance
     * @return the nearest CustomVertex to vFrom
     * @throws Exception if no suitable vertex is found or if the nearest vertex is more than
     *                   500 meters away, indicating the vertex is out of range
     */
    public CustomVertex nearestVertex(V vFrom) throws Exception {
        CustomVertex from = (CustomVertex) vFrom;
        CustomVertex vBest = null;
        double bestDistance = Double.MAX_VALUE;
        // loop over available vertices in graph, calculate distance to vFrom and keep nearest vertex
        for(V to : this.vertexSet()) {
            CustomVertex vTo = (CustomVertex) to;
            double dist = CustomVertex.distance(from, vTo);
            if(vBest == null || dist < bestDistance) {
                bestDistance = dist;
                vBest = vTo;
            }
        }
        // check if nearest vertex is located more than 500 meters away from desire position
        if(CustomVertex.distance(from, vBest) > 500) throw new Exception("ADDRESS_OUT_OF_RANGE");
        return vBest;
    }
    
}
