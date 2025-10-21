package ch.routify.routing;

import java.util.HashMap;
import java.util.HashSet;
import org.jgrapht.GraphPath;
import org.jgrapht.alg.interfaces.AStarAdmissibleHeuristic;
import org.jgrapht.alg.shortestpath.ALTAdmissibleHeuristic;
import org.jgrapht.alg.shortestpath.AStarShortestPath;
import org.jgrapht.graph.AsWeightedGraph;

import ch.routify.graph.CustomAsSubgraph;
import ch.routify.graph.CustomEdge;
import ch.routify.graph.CustomVertex;

/**
 * Provides routing functionalities using graph-based algorithms and custom criteria.
 * This class includes methods for calculating routes based on various environmental factors
 * like slope, green index, noise, air quality, and traffic. It integrates with the JGraphT library
 * to perform graph operations and utilizes custom classes for vertices, edges, and subgraphs.
 */
public class Routing {

    /**
     * Calculates the shortest path between two points using the A* algorithm and an admissible heuristic.
     * 
     * @param cFrom The starting point as a {@link CustomVertex}.
     * @param cTo The ending point as a {@link CustomVertex}.
     * @param weights A {@link HashMap} containing the weights of the edges.
     * @param graph The graph represented as a {@link CustomAsSubgraph}.
     * @return A {@link GraphPath} representing the shortest path between the two points.
     * @throws Exception if the path cannot be calculated.
     */
    public static GraphPath<CustomVertex, CustomEdge> aStar(CustomVertex cFrom, CustomVertex cTo, HashMap<CustomEdge, Double> weights, 
        CustomAsSubgraph<CustomVertex, CustomEdge> graph) throws Exception {
        
        CustomVertex start = graph.nearestVertex(cFrom);
        CustomVertex end = graph.nearestVertex(cTo);

        AsWeightedGraph<CustomVertex, CustomEdge> weighted_graph = new AsWeightedGraph<CustomVertex, CustomEdge>(graph, weights, false);
        
        HashSet<CustomVertex> landmarks = new HashSet<CustomVertex>();
        landmarks.add(start);
        landmarks.add(end);
        
        AStarAdmissibleHeuristic<CustomVertex>  heuristic = new ALTAdmissibleHeuristic<>(weighted_graph, landmarks);
        AStarShortestPath<CustomVertex, CustomEdge> astar = new AStarShortestPath<>(weighted_graph, heuristic);
        GraphPath<CustomVertex, CustomEdge> graphPath = astar.getPath(start, end);

        return graphPath;
    }
}
