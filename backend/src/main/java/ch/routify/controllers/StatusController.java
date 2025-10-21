package ch.routify.controllers;

import java.io.FileNotFoundException;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import ch.routify.Routify;
import net.minidev.json.JSONObject;
import net.minidev.json.parser.ParseException;

/**
 * Controller responsible for handling API endpoints related to the system status within the COSS Maps application.
 * This controller provides endpoints for retrieving general system status information such as vertex and edge counts in the system's graph,
 * as well as detailed boundary information.
 * 
 * @author Alexander Eggerth
 * @version 1.0
 */
@RestController
@CrossOrigin("*")
@RequestMapping("/status")
public class StatusController {
    
    /**
     * Retrieves the current status of the system, including counts of vertices and edges in the graph.
     * 
     * @return ResponseEntity containing a {@link JSONObject} with the vertex and edge count of the system's graph,
     *         wrapped in an HTTP OK response.
     */
    @GetMapping(path="/")
    public ResponseEntity<JSONObject> getStatus() {
        JSONObject response = new JSONObject();
        response.put("vertex_count", Routify.sys.getGraph().vertexSet().size());
        response.put("edge_count", Routify.sys.getGraph().edgeSet().size());
        return new ResponseEntity<>(response, HttpStatus.OK);
    }

    /**
     * Retrieves the geographical boundary information for the system.
     * 
     * @return ResponseEntity containing a {@link JSONObject} with the system's boundary information,
     *         wrapped in an HTTP OK response.
     * @throws FileNotFoundException if the boundary information file cannot be found.
     * @throws ParseException if there is an error parsing the boundary information file.
     */
    @GetMapping(path="/boundary/")
    public ResponseEntity<JSONObject> getBoundary() throws FileNotFoundException, ParseException {
        Routify.logger.info("Boundary of loaded dataset has been requested");
        return new ResponseEntity<>(Routify.sys.getBoundary(), HttpStatus.OK);
    }

    /**
     * Triggers update of cached metadata and updates graph datastructure according to new metadata.
     * @return ResponseEntity containing a empty {@link JSONObject}
     * @throws Exception 
     */
    @GetMapping(path="/fetchmeta/")
    public ResponseEntity<JSONObject> fetchMeta() throws Exception {
        Routify.sys.fetchMetaData();
        Routify.logger.info("Metadata has been fetched from filesystem");
        return new ResponseEntity<>(new JSONObject(), HttpStatus.OK);
    }

}
