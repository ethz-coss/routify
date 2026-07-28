package ch.routify.controllers;

import java.io.FileNotFoundException;
import java.io.IOException;
import java.io.OutputStream;

import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

import ch.routify.Routify;
import net.minidev.json.JSONObject;
import net.minidev.json.parser.ParseException;

/**
 * Controller responsible for handling API endpoints related to the system status within the Routifys application.
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

    /**
     * Streams the complete routing graph as a single JSON document with two arrays
     * (vertices and edges). Intended for offline analysis: the response can be
     * piped straight to disk (e.g. {@code curl > graph.json}) without the
     * backend buffering the whole payload in memory.
     *
     * @return streaming JSON body produced by {@link ch.routify.graph.CustomGraph#exportJson(OutputStream)}
     */
    @GetMapping(path="/graph/", produces=MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<StreamingResponseBody> getGraph() {
        Routify.logger.info("Full graph export has been requested");
        StreamingResponseBody body = (OutputStream out) -> {
            try {
                Routify.sys.getGraph().exportJson(out);
            } catch (IOException e) {
                Routify.logger.error("Error while streaming graph JSON", e);
                throw e;
            }
        };
        return new ResponseEntity<>(body, HttpStatus.OK);
    }

}
