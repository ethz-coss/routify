package ch.routify.routing;

import ch.routify.graph.CustomEdge;
import lombok.Getter;
import net.minidev.json.JSONArray;

@Getter
public class Directions {
    @Getter
    public JSONArray directions = new JSONArray();
    private DirectionSegment lastSegment = null;
    
    public Directions(CustomRoute route) {
        
        for(CustomEdge edge : route.getEdges()) {
            lastSegment = new DirectionSegment(edge);
            directions.add(lastSegment);
        }
    }

    // Manual getter method (Lombok not working properly)
    public JSONArray getDirections() {
        return directions;
    }
}
