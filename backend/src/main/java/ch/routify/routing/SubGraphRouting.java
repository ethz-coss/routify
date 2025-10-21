package ch.routify.routing;

import java.util.HashSet;
import java.util.Set;

import ch.routify.Routify;
import ch.routify.graph.CustomAsSubgraph;
import ch.routify.graph.CustomEdge;
import ch.routify.graph.CustomVertex;

/**
 * Provides functionality for calculating a subgraph between two points using a heuristic based on convex/concave routing behavior.
 */
public class SubGraphRouting {

    /**
     * Calculates and returns a subgraph of the main graph centered around the midpoint between an origin and destination vertex.
     * The subgraph includes vertices within a certain distance from the midpoint, effectively capturing a subset of the graph
     * that is likely to contain the route between the origin and destination.
     * 
     * This method is useful for reducing the computational complexity of routing algorithms by focusing on a smaller, relevant portion of the graph.
     * 
     * @param origin The starting point of the route as a {@link CustomVertex}.
     * @param dest The ending point of the route as a {@link CustomVertex}.
     * @return A {@link CustomAsSubgraph} containing the vertices and edges that form the subgraph between the specified origin and destination.
     * @throws Exception 
     */
    public static CustomAsSubgraph<CustomVertex, CustomEdge> getSubGraph(CustomVertex origin, CustomVertex dest) throws Exception {
        double distance = CustomVertex.distance(origin, dest);

        double lat = (origin.getLat() + dest.getLat()) / 2;
        double lon = (origin.getLon() + dest.getLon()) / 2;

        CustomVertex vCenter = Routify.vertexFactory.createObject(lat, lon, 0L);

        Set<CustomVertex> vertexSetSubgraph = new HashSet<CustomVertex>();
        for(CustomVertex v : Routify.sys.getGraph().vertexSet()) {
            if(CustomVertex.distance(vCenter, v) < ((distance / 2) + 500.0)) {
                vertexSetSubgraph.add(v);
            }
        }

        CustomAsSubgraph<CustomVertex, CustomEdge> subgraph = new CustomAsSubgraph<CustomVertex, CustomEdge>(Routify.sys.getGraph(), vertexSetSubgraph);

        return subgraph;
    }

}