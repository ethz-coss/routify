package ch.routify.routing;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import org.jgrapht.GraphPath;

import ch.routify.graph.CustomAsSubgraph;
import ch.routify.graph.CustomEdge;
import ch.routify.graph.CustomVertex;
import lombok.Getter;
import lombok.Setter;
import lombok.ToString;
import net.minidev.json.JSONArray;
import net.minidev.json.JSONObject;
import scala.Tuple2;

@Getter
@Setter
@ToString
public class CustomRoute {
    private List<CustomVertex> vertices;
    private List<CustomEdge> edges;

    private CustomEdge startEdge;
    private CustomEdge endEdge;
    private CustomVertex startVertex;
    private CustomVertex endVertex;
    private CustomVertex originalStartVertex;
    private CustomVertex originalEndVertex;

    private String routingMode;
    private String transportMode;

    private double traveltime = 0;

    private JSONArray directions;
    
    private boolean includeTraveltime;
    private boolean includeDirections;

    public CustomRoute (JSONObject data, Tuple2<CustomVertex, CustomVertex> endpoints, CustomAsSubgraph<CustomVertex, CustomEdge> graph, 
        HashMap<CustomEdge, Double> weights, String routingMode, String transportMode, boolean includeDirections, boolean includeTraveltime) throws Exception {

        this.routingMode = routingMode;
        this.transportMode = transportMode;
        this.includeTraveltime = includeTraveltime;
        this.includeDirections = includeDirections;
        
        this.calculate(data, endpoints, graph, weights, routingMode, transportMode, includeDirections, includeTraveltime);
    }
    
    private void calculate(JSONObject data, Tuple2<CustomVertex, CustomVertex> endpoints, CustomAsSubgraph<CustomVertex, CustomEdge> graph, 
        HashMap<CustomEdge, Double> weights, String routing_mode, String transport_mode, boolean includeDirections, boolean includeTraveltime) throws Exception {
                
        HashMap<CustomEdge, Double> tmpWeights = new HashMap<CustomEdge, Double>();
        WeightSupplier ws = new WeightSupplier(graph.edgeSet(), weights);

        switch(routing_mode) {
            case "routing_mode_slope":
                double slope = Double.valueOf(data.get("slope").toString());
                tmpWeights = ws.slope(slope);
            break;
            case "routing_mode_green":
                double green_index = Double.valueOf(data.get("green_index").toString());
                tmpWeights = ws.greenIndex(green_index);
            break;
            case "routing_mode_noise":
                double noise = Double.valueOf(data.get("noise").toString());
                tmpWeights = ws.noise(noise);
            break;
            case "routing_mode_air":
                double air = Double.valueOf(data.get("air").toString());
                tmpWeights = ws.air(air);
            break;
            case "routing_mode_feedback_ci":
                double feedbackCi = Double.valueOf(data.get("feedback").toString());
                tmpWeights = ws.feedbackCi(feedbackCi);
            break;
            case "routing_mode_feedback_twa":
                double feedbackTwa = Double.valueOf(data.get("feedback").toString());
                tmpWeights = ws.feedbackCi(feedbackTwa);
            break;
            default:
                tmpWeights = weights;
            break;
        }

        GraphPath<CustomVertex, CustomEdge> graphPath = Routing.aStar(endpoints._1(), endpoints._2(), tmpWeights, graph);
        if(graphPath.getLength() == 0) throw new Exception("THERE_EXISTS_NO_PATH");

        this.edges = graphPath.getEdgeList();
        this.startEdge = edges.get(0);
        this.endEdge = edges.get(edges.size() - 1);
        // remove first and last edge because they are only used to connect user input to graph

        this.vertices = graphPath.getVertexList();
        this.startVertex = graphPath.getStartVertex();
        this.endVertex = graphPath.getEndVertex();
        
        // Store original exact coordinates for start and end points
        this.originalStartVertex = endpoints._1();
        this.originalEndVertex = endpoints._2();
        // remove vertices that do not contain meta data because they represent the user input coordinates

        // calculate traveltime (if not preset and traveltime is requested)
        if(this.traveltime == 0 && includeTraveltime) {
            for(CustomEdge e : this.edges) {
                this.traveltime += e.getTravelTime(this.transportMode);
            }
        } else if (!includeTraveltime) {
            this.traveltime = 0.0; // Set to 0 when traveltime not requested
        }

        // Generate directions only if requested
        if (includeDirections) {
            this.directions = new Directions(this).getDirections();
        } else {
            this.directions = new JSONArray(); // Empty array when directions not requested
        }
    }

    /**
     * Returns a JSON representation of the route with conditional travel time information.
     * This method ensures that travel time information is only included when requested.
     * 
     * @return JSONObject representing the route with conditional travel time.
     */
    public JSONObject toJSON() {
        JSONObject routeJson = new JSONObject();
        
        // Add basic route information
        routeJson.put("routingMode", this.routingMode);
        routeJson.put("transportMode", this.transportMode);
        
        // Add travel time only if requested
        if (this.includeTraveltime) {
            routeJson.put("traveltime", this.traveltime);
        }
        
        // Add directions only if requested
        if (this.includeDirections && this.directions != null && this.directions.size() > 0) {
            routeJson.put("directions", this.directions);
        }
        
        // Add vertices
        JSONArray verticesJson = new JSONArray();
        for (CustomVertex vertex : this.vertices) {
            JSONObject vertexJson = new JSONObject();
            vertexJson.put("lat", vertex.getLat());
            vertexJson.put("lon", vertex.getLon());
            vertexJson.put("id", vertex.getId());
            vertexJson.put("altitude", vertex.getAltitude());
            vertexJson.put("noise", vertex.getNoise());
            vertexJson.put("pm_10", vertex.getPm10());
            vertexJson.put("osmId", vertex.getOsmId());
            verticesJson.add(vertexJson);
        }
        routeJson.put("vertices", verticesJson);
        
        // Add start and end vertices using original exact coordinates
        JSONObject startVertexJson = new JSONObject();
        startVertexJson.put("lat", this.originalStartVertex.getLat());
        startVertexJson.put("lon", this.originalStartVertex.getLon());
        startVertexJson.put("id", this.originalStartVertex.getId());
        startVertexJson.put("altitude", this.originalStartVertex.getAltitude());
        startVertexJson.put("noise", this.originalStartVertex.getNoise());
        startVertexJson.put("pm_10", this.originalStartVertex.getPm10());
        startVertexJson.put("osmId", this.originalStartVertex.getOsmId());
        routeJson.put("startVertex", startVertexJson);
        
        JSONObject endVertexJson = new JSONObject();
        endVertexJson.put("lat", this.originalEndVertex.getLat());
        endVertexJson.put("lon", this.originalEndVertex.getLon());
        endVertexJson.put("id", this.originalEndVertex.getId());
        endVertexJson.put("altitude", this.originalEndVertex.getAltitude());
        endVertexJson.put("noise", this.originalEndVertex.getNoise());
        endVertexJson.put("pm_10", this.originalEndVertex.getPm10());
        endVertexJson.put("osmId", this.originalEndVertex.getOsmId());
        routeJson.put("endVertex", endVertexJson);
        
        // Add edges with conditional travel time
        JSONArray edgesJson = new JSONArray();
        for (CustomEdge edge : this.edges) {
            JSONObject edgeJson = new JSONObject();
            edgeJson.put("id", edge.getId());
            edgeJson.put("osmId", edge.getOsmId());
            edgeJson.put("tag", edge.getTags());
            edgeJson.put("distance", edge.getDistance());
            edgeJson.put("slope", edge.getSlope());
            edgeJson.put("noise", edge.getNoise());
            edgeJson.put("greenIndex", edge.getGreenIndex());
            edgeJson.put("aqius", edge.getAqius());
            edgeJson.put("highway", edge.getHighway());
            edgeJson.put("maxspeed", edge.getMaxspeed());
            edgeJson.put("feedbackCi", edge.getFeedbackCi());
            edgeJson.put("feedbackTwa", edge.getFeedbackTwa());
            edgeJson.put("bearing", edge.getBearing());
            edgeJson.put("cardinalDirection", edge.getCardinalDirection());
            edgeJson.put("pm_10", edge.getPm_10());
            
            // Add source vertex
            JSONObject sourceVertex = new JSONObject();
            sourceVertex.put("lat", edge.getSourceVertex().getLat());
            sourceVertex.put("lon", edge.getSourceVertex().getLon());
            sourceVertex.put("osmId", edge.getSourceVertex().getOsmId());
            edgeJson.put("source", sourceVertex);
            
            // Add target vertex
            JSONObject targetVertex = new JSONObject();
            targetVertex.put("lat", edge.getTargetVertex().getLat());
            targetVertex.put("lon", edge.getTargetVertex().getLon());
            targetVertex.put("osmId", edge.getTargetVertex().getOsmId());
            targetVertex.put("noise", edge.getTargetVertex().getNoise());
            targetVertex.put("altitude", edge.getTargetVertex().getAltitude());
            edgeJson.put("target", targetVertex);
            
            // Add travel time information only if requested
            HashMap<String, Double> travelTimeMap = edge.getTraveltime(this.includeTraveltime);
            if (travelTimeMap != null) {
                edgeJson.put("traveltime", travelTimeMap);
            }
            
            edgesJson.add(edgeJson);
        }
        routeJson.put("edges", edgesJson);
        
        return routeJson;
    }

    /**
     * Override toString to use custom JSON serialization.
     * This ensures that our conditional travel time logic is used.
     */
    @Override
    public String toString() {
        return toJSON().toJSONString();
    }

    // Manual getter method (Lombok not working properly)
    public List<CustomEdge> getEdges() {
        return edges;
    }
    
    // Manual getter methods for original vertices (Lombok not working properly)
    public CustomVertex getOriginalStartVertex() {
        return originalStartVertex;
    }
    
    public CustomVertex getOriginalEndVertex() {
        return originalEndVertex;
    }
}
