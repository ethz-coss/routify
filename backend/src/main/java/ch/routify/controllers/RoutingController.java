package ch.routify.controllers;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import ch.routify.Routify;
import ch.routify.graph.CustomAsSubgraph;
import ch.routify.graph.CustomEdge;
import ch.routify.graph.CustomVertex;
import ch.routify.revgeocode.RevGeoCode;
import ch.routify.routing.CallableRouting;
import ch.routify.routing.CustomRoute;
import ch.routify.routing.SubGraphRouting;
import ch.routify.routing.config.RoutingModeService;
import net.minidev.json.JSONArray;
import net.minidev.json.JSONObject;
import net.minidev.json.parser.JSONParser;
import scala.Tuple2;

/**
 * Handles routing-related API endpoints for the COSS Maps application.
 * This controller is responsible for processing incoming requests to calculate routes based on different criteria
 * such as distance, greenery, slope, noise, air quality, and traffic conditions. It supports multiple routing modes
 * to provide users with the best possible paths according to their preferences.
 * <p>
 * This class utilizes an ExecutorService to handle route calculations in parallel, improving performance
 * and responsiveness of the routing API. Each routing mode endpoint accepts a request body containing
 * the necessary information to compute the route and returns a JSON object with the route information.
 * <p>
 * In case of errors during route calculation, it responds with an appropriate error message and HTTP status code.
 * 
 * @author Alexander Eggerth
 * @version 1.0
 */
@RestController
@CrossOrigin("*")
@RequestMapping("/route")
public class RoutingController {

    private final RoutingModeService routingModeService = new RoutingModeService();

    @PostMapping(value = "{routingMode}/")
    public ResponseEntity<JSONArray> calcRoute(@PathVariable String routingMode, @RequestBody String request,
            @RequestParam(defaultValue = "true") boolean directions,
            @RequestParam(defaultValue = "true") boolean traveltime) throws Exception {
        if (!routingModeService.hasMode(routingMode)) {
            return ResponseEntity.notFound().build();
        }
        return buildResponseEntity(request, routingMode, directions, traveltime);
    }

    /**
     * Constructs the ResponseEntity object for the given request and routing mode.
     * This method processes the request, calculates the route based on the specified mode,
     * and prepares the response to be sent back to the client.
     * 
     * @param request The JSON string request from the client.
     * @param routingMode The routing mode indicating the optimization criterion.
     * @param directions Whether to include directions in the response (default: true).
     * @param traveltime Whether to include travel time in the response (default: true).
     * @return ResponseEntity with the calculated route as a JSONObject.
     */
    private ResponseEntity<JSONArray> buildResponseEntity(String request, String routingMode, boolean directions, boolean traveltime) {
        JSONArray response = new JSONArray();
        try {
            response = handleRequest(request, routingMode, directions, traveltime);
        } catch(Exception e) {
            Routify.logger.error("Error processing routing request for mode: {}", routingMode, e);
            response.add(e);
            return ResponseEntity.badRequest().header("Content-Type", "application/json").body(response);
        }
        return ResponseEntity.ok()
        .header("Content-Type", "application/json")
        .body(response);
    }

    /**
     * Handles the route calculation request for a given mode.
     * This method parses the request, sets up the necessary subgraph for route calculation,
     * and executes the routing in parallel for different transport modes. It compiles the
     * routes into a single response object.
     * 
     * @param request The JSON string request containing the necessary information for route calculation.
     * @param mode The routing mode.
     * @param directions Whether to include directions in the response.
     * @param traveltime Whether to include travel time in the response.
     * @return JSONObject containing the route(s) calculated.
     * @throws Exception if there is an error parsing the request or calculating the route.
     */
    private JSONArray handleRequest(String request, String mode, boolean directions, boolean traveltime) throws Exception {
        JSONObject data = (JSONObject) new JSONParser(JSONParser.MODE_JSON_SIMPLE).parse(request);
        
        // define subgraph needed to compute route for specific request
        Tuple2<CustomVertex, CustomVertex> endpoints = RevGeoCode.resolveRequestAddresses(data);
        CustomAsSubgraph<CustomVertex, CustomEdge> subgraph = SubGraphRouting.getSubGraph(endpoints._1(), endpoints._2());
        
        // define executor service to calculate shortest paths for different transport_modes in parallel
        int numberOfThreads = 3;
        ExecutorService executorService = Executors.newFixedThreadPool(numberOfThreads);
        
        CallableRouting c_walk = new CallableRouting(subgraph, data, endpoints, Routify.sys.getWeightsWalk(), mode,
                "transport_mode_walk", directions, traveltime, routingModeService,
                Routify.sys.getAllowedFeaturesForTransportMode("transport_mode_walk"));
        CallableRouting c_cycle = new CallableRouting(subgraph, data, endpoints, Routify.sys.getWeightsBike(), mode,
                "transport_mode_cycle", directions, traveltime, routingModeService,
                Routify.sys.getAllowedFeaturesForTransportMode("transport_mode_cycle"));
        CallableRouting c_drive = new CallableRouting(subgraph, data, endpoints, Routify.sys.getWeightsDrive(), mode,
                "transport_mode_drive", directions, traveltime, routingModeService,
                Routify.sys.getAllowedFeaturesForTransportMode("transport_mode_drive"));
        
        Future<CustomRoute> f_walk = executorService.submit(c_walk);
        Future<CustomRoute> f_cycle = executorService.submit(c_cycle);
        Future<CustomRoute> f_drive = executorService.submit(c_drive);
        
        JSONArray routes = new JSONArray();
        routes.add(f_walk.get().toJSON());
        routes.add(f_cycle.get().toJSON());
        routes.add(f_drive.get().toJSON());
        executorService.shutdown();
        
        Routify.logger.info(String.format("computed route (%s)", mode));
        return routes;
    }
}
