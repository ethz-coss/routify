package ch.routify.controllers;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import ch.routify.Routify;
import ch.routify.graph.CustomEdge;
import ch.routify.graph.CustomVertex;
import net.minidev.json.JSONArray;
import net.minidev.json.JSONObject;

/**
 * Controller responsible for handling API endpoints related to querying geographical data.
 * It provides functionalities for finding nearby entities based on latitude and longitude coordinates.
 * Utilizes {@link Routify} for geographic calculations and data retrieval.
 * 
 * @author Alexander Eggerth
 * @version 1.0
 */
@RestController
@CrossOrigin("*")
@RequestMapping("/query")
public class QueryController {

    /**
     * Retrieves a list of edges in range of 30 meters based on the provided latitude and longitude.
     * 
     * @param lat The latitude of the point to find nearby edges for, as a {@link String}.
     * @param lon The longitude of the point to find nearby edges for, as a {@link String}.
     * @return A {@link ResponseEntity} containing a {@link JSONArray} with a list of {@link CustomEdge} objects.
     */
    @GetMapping(path="/nearby/")
    public ResponseEntity<JSONArray> getStatus(@RequestParam("lat") String lat, @RequestParam("lon") String lon) {
        CustomVertex v0 = Routify.vertexFactory.createObject(Double.valueOf(lat), Double.valueOf(lon), 0L);
        JSONArray inRange = new JSONArray();
        for(CustomEdge e : Routify.sys.getGraph().edgeSet()) {
            try {
                if(CustomVertex.distance(v0, e.getSourceVertex()) <= 30) {
                // edge in range
                    inRange.add(e);
                }
            } catch (Exception exception) {}
        }
        return new ResponseEntity<>(inRange, HttpStatus.OK);
    }

    @GetMapping(path="/edge/")
    public ResponseEntity<JSONObject> getNode(@RequestParam("id") Long id) {
        JSONObject response = new JSONObject();
        CustomEdge edge = CustomEdge.getById(id);
        response.put("slope", edge.getSlope());
        return new ResponseEntity<>(response, HttpStatus.OK);
    }
    
}
