package ch.routify.routing;

import java.util.HashMap;
import java.util.concurrent.Callable;

import ch.routify.graph.CustomAsSubgraph;
import ch.routify.graph.CustomEdge;
import ch.routify.graph.CustomVertex;
import net.minidev.json.JSONObject;
import scala.Tuple2;

/**
 * The {@code CallableRouting} class implements the {@code Callable} interface,
 * providing a way to compute routing asynchronously. It encapsulates the routing
 * calculation logic, allowing it to be executed in parallel or on a separate thread,
 * returning a {@code JSONObject} that contains the routing result.
 */
public class CallableRouting implements Callable<CustomRoute> {
    /** The graph on which the routing calculation is based. */
    private CustomAsSubgraph<CustomVertex, CustomEdge> graph;
    /** Additional data required for routing calculation. */
    private JSONObject data;
    /** The starting and ending vertices for the routing. */
    private Tuple2<CustomVertex, CustomVertex> endpoints;
    /** The routing mode specifies how the routing should be performed. */
    private String routing_mode;
    /** The mode of transport to be used for routing. */
    private String transport_mode;
    /** A map of weights associated with the edges in the graph. */
    private HashMap<CustomEdge, Double> weights;
    /** Whether to include directions in the response. */
    private boolean directions;
    /** Whether to include travel time in the response. */
    private boolean traveltime;

    /**
     * Constructs a new instance of {@code CallableRouting} with the specified parameters.
     *
     * @param _graph          The graph on which to perform the routing.
     * @param _data           Additional data required for the routing calculation.
     * @param _endpoints      The starting and ending vertices for the routing.
     * @param _weights        The weights associated with the edges in the graph.
     * @param _routing_mode   The routing mode to be used.
     * @param _transport_mode The transport mode to be used for routing.
     * @param _directions     Whether to include directions in the response.
     * @param _traveltime     Whether to include travel time in the response.
     */
    public CallableRouting(CustomAsSubgraph<CustomVertex, CustomEdge> _graph, JSONObject _data, Tuple2<CustomVertex, CustomVertex> _endpoints, HashMap<CustomEdge, Double> _weights, String _routing_mode, String _transport_mode, boolean _directions, boolean _traveltime) {
        this.graph = _graph;
        this.data = _data;
        this.endpoints = _endpoints;
        this.weights = _weights;
        this.routing_mode = _routing_mode;
        this.transport_mode = _transport_mode;
        this.directions = _directions;
        this.traveltime = _traveltime;
    }

    /**
     * Executes the routing calculation.
     *
     * @return A {@code JSONObject} containing the results of the routing calculation.
     * @throws Exception if an error occurs during the routing calculation.
     */
    @Override
    public CustomRoute call() throws Exception {
        return new CustomRoute(data, endpoints, graph, weights, routing_mode, transport_mode, directions, traveltime);
    }    
}
