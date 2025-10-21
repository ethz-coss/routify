package ch.routify.osmparser;

import ch.routify.graph.CustomVertex;
import ch.routify.Routify;
import ch.routify.RoutifySystem;
import ch.routify.graph.CustomEdge;
import ch.routify.graph.CustomGraph;
import net.minidev.json.JSONArray;
import net.minidev.json.JSONObject;
import net.minidev.json.parser.JSONParser;
import net.minidev.json.parser.ParseException;

import java.io.FileNotFoundException;
import java.io.FileWriter;
import java.io.IOException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;

/**
 * Parses OSM raw output from the Overpass Turbo API and initializes a graph
 * representation of the data. It supports handling nodes and ways to construct
 * vertices and edges in the graph.
 */
public class OsmParser {
    private JSONArray nodes;
    private JSONArray ways;

    /**
     * Main method to demonstrate the usage of OsmParser.
     * 
     * @param args Command line arguments (not used).
     * @throws FileNotFoundException If the source file is not found.
     * @throws ParseException If parsing the JSON data fails.
     * @throws IOException If an I/O error occurs.
     */
    public static void main(String[] args) throws FileNotFoundException, ParseException, IOException {
        OsmParser bmp = new OsmParser("/home/aeggerth/GitHub/coss-maps-backend/src/main/resources/static/basemap_admin_level_8.json");
        // CustomGraph<CustomVertex, CustomEdge> graph = new CustomGraph<>(CustomEdge.class);
        // bmp.initializeGraph(graph);
        bmp.exportOsmIdToCoordinates("/home/aeggerth/GitHub/coss-maps-backend/src/main/resources/static/osmid_to_coordinates_admin_level_8.json");
        bmp.clear();
    }

    public JSONArray getNodes() {
        return this.nodes;
    }

    public JSONArray getWays() {
        return this.ways;
    }

    /**
     * Constructs an OsmParser and loads data from a specified source file.
     * 
     * @param pathOfSourceFile Path to the GeoJSON file containing OSM data.
     * @throws FileNotFoundException If the source file is not found.
     * @throws ParseException If parsing the JSON data fails.
     */
    public OsmParser(String pathOfSourceFile) throws FileNotFoundException, ParseException {
        this.ways = new JSONArray();
        this.nodes = new JSONArray();

        JSONObject jsonData = (JSONObject) new JSONParser(JSONParser.MODE_JSON_SIMPLE).parse(RoutifySystem.getReader(pathOfSourceFile));
        JSONArray elements = (JSONArray) jsonData.get("elements");
        jsonData.clear();
        for(Object o : elements) {
            JSONObject element = (JSONObject) o;
            if(element.get("type").equals("way")) this.ways.add(element);
            if(element.get("type").equals("node")) this.nodes.add(element);
        }
        elements.clear();
    }

    /**
     * Initializes the graph with vertices and edges based on the parsed OSM data.
     * 
     * @param graph The graph to be initialized.
     */
    public void initializeGraph(CustomGraph<CustomVertex, CustomEdge> graph) {
        long startTime = System.nanoTime();
        HashMap<Long, CustomVertex> idToVertex = new HashMap<>();
        // add vertices to graph
        for(Object o : this.nodes) {
            JSONObject node = (JSONObject) o;
            Long nodeId = (Long) node.get("id");
            CustomVertex vertex = Routify.vertexFactory.createObject((double) node.get("lat"), (double) node.get("lon"), nodeId);
            idToVertex.put(nodeId, vertex);
            graph.addVertex(vertex);
        }
        // add edges to graph
        int noname = 0;
        for(Object o : this.ways) {
            JSONObject way = (JSONObject) o;
            JSONArray nodes = (JSONArray) way.get("nodes");
            JSONObject tags = (JSONObject) way.get("tags");
            if(tags.get("name") == null) noname++;
            CustomVertex previous = null;
            for(Object i: nodes) {
                Long nodeId = (Long) i;
                try {
                    CustomVertex vertex = idToVertex.get(nodeId);
                    if(previous != null) {

                        // check if way is publicly accessible
                        String access = (String) tags.get("access");
                        if(access == null || (!access.equals("private") && !access.equals("permissive") && !access.equals("no"))) {

                            graph.addEdge(previous, vertex, new CustomEdge(previous, vertex, tags, (Long) way.get("id")));

                            // if not unidirectional add second direction
                            if(tags.get("oneway") == null || !tags.get("oneway").equals("yes")) {
                                graph.addEdge(vertex, previous, new CustomEdge(vertex, previous, tags, (Long) way.get("id")));
                            }

                        }
                    }
                    previous = vertex;
                } catch (Exception e) {
                    Routify.logger.warn(String.format("[BasemapParser] skipped edge (osm_id=%d)", nodeId));
                }
            }
        }
        idToVertex.clear();
        long endTime = System.nanoTime();
        double executionTimeInSeconds = (endTime - startTime) / 1_000_000_000.0;
        Routify.logger.info(String.format("[BasemapParser] initialized graph with #vertices=%d, #edges=%d in %f seconds", graph.vertexSet().size(), graph.edgeSet().size(), executionTimeInSeconds));
        Routify.logger.debug("Out of {} ways, {} have no name", this.ways.size(), noname);
    }

    /**
     * Clears internal data structures to release memory.
     */
    public void clear() {
        this.nodes.clear();
        this.ways.clear();
        Routify.logger.info("[BasemapParser] released memory used for intermediate data structures");
    }

    /**
     * Exports a mapping of OSM IDs to their corresponding latitude and longitude coordinates to a specified file.
     * The method iterates over a collection of nodes, each represented as a JSONObject, extracting the OSM ID, latitude, and longitude.
     * These details are then formatted and written to a file in a JSON structure.
     * 
     * @param path The file system path where the exported JSON file will be saved. It specifies the location and name of the file.
     *             The method assumes that the path is valid and that it has the necessary permissions to write to it.
     * @throws IOException If an I/O error occurs during writing to the file. This includes cases where the file cannot be opened for writing,
     *                     if there is an error during writing to the file, or if the file cannot be closed.
     */
    public void exportOsmIdToCoordinates(String path) {
    try (FileWriter file = new FileWriter(path)) {
        file.write("{\n");
        
        List<Object> nodes = new ArrayList<>(this.getNodes()); // Convert to List if necessary
        int size = nodes.size();
        
        for (int i = 0; i < size; i++) {
            JSONObject node = (JSONObject) nodes.get(i);
            if (i < size - 1) {
                // Not the last element
                file.write(String.format("\t\"%d\" : { \"lat\" : %f, \"lon\" : %f },\n", node.get("id"), (double) node.get("lat"), (double) node.get("lon")));
            } else {
                // The last element, handle differently if needed (e.g., omitting the trailing comma)
                file.write(String.format("\t\"%d\" : { \"lat\" : %f, \"lon\" : %f }\n", node.get("id"), (double) node.get("lat"), (double) node.get("lon")));
            }
        }
        
        file.write("}");
        file.flush();
    } catch (Exception e) {
        Routify.logger.error("could not export osmId to coordinates map", e);
    }
}

}
