package ch.routify.graph;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.io.OutputStreamWriter;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import javax.xml.parsers.FactoryConfigurationError;
import javax.xml.stream.XMLStreamException;
import javax.xml.stream.XMLStreamWriter;

import org.jgrapht.alg.connectivity.ConnectivityInspector;
import org.jgrapht.graph.SimpleDirectedWeightedGraph;
import org.jgrapht.nio.gexf.GEXFExporter.Parameter;

import ch.routify.Routify;
import net.minidev.json.JSONObject;
import net.sf.saxon.s9api.Processor;
import net.sf.saxon.s9api.SaxonApiException;
import net.sf.saxon.s9api.Serializer;
import net.sf.saxon.s9api.Serializer.Property;

/**
 * A generic class that extends SimpleDirectedWeightedGraph to manage and manipulate graphs.
 * It provides functionalities such as adding edges, finding the nearest vertex, exporting the graph in GEXF format, and cleaning up disjoint sets.
 * 
 * @param <V> the vertex class, which should extend CustomVertex
 * @param <E> the edge class, which should extend CustomEdge
 * @author Alexander Eggerth
 * @version 1.0
 */
public class CustomGraph<V, E> extends SimpleDirectedWeightedGraph<V, E> {

    /**
     * Constructs a CustomGraph with the specified edge class.
     * 
     * @param edgeClass the class of edges to be used in the graph
     */
    public CustomGraph(Class<? extends E> edgeClass) {
        super(edgeClass);
    }

    /**
     * Adds an edge between source and target vertices. Prints a message if either vertex is null.
     * 
     * @param sourceVertex the source vertex of the edge
     * @param targetVertex the target vertex of the edge
     * @return the added edge, or null if no edge was added
     */
    @Override
    public E addEdge(V sourceVertex, V targetVertex) {
        if(sourceVertex == null || targetVertex == null) {
            Routify.logger.warn("Attempted to add edge with null vertex");
        }
        E edge = super.addEdge(sourceVertex, targetVertex);
        return edge;
    }

    /**
     * Finds the nearest vertex to the given vertex.
     * 
     * @param from the vertex from which to search
     * @return the nearest vertex to the specified vertex
     * @throws Exception if the nearest vertex is more than 500 meters away
     */
    public CustomVertex nearestVertex(V from) throws Exception {
        CustomVertex vFrom = (CustomVertex) from;
        CustomVertex vBest = null;
        double bestDistance = Double.MAX_VALUE;
        for(V to : this.vertexSet()) {
            CustomVertex vTo = (CustomVertex) to;
            double dist = CustomVertex.distance(vFrom, vTo);
            if(vBest == null || dist < bestDistance) {
                bestDistance = dist;
                vBest = vTo;
            }
            if(bestDistance < 1.0) return vBest;
        }
        // check if nearest vertex is located more than 500 meters away from desire position
        if(CustomVertex.distance(vFrom, vBest) > 500) throw new Exception("ADDRESS_OUT_OF_RANGE");
        return vBest;
    }

    /**
     * Exports the graph to a GEXF file with a default filename based on the current date.
     * 
     * @throws IOException if an I/O error occurs
     * @throws XMLStreamException if an error occurs while processing the XML
     * @throws FactoryConfigurationError if a configuration error occurs
     * @throws SaxonApiException if an error occurs while using the Saxon API
     */
    public void exportGexf() throws IOException, XMLStreamException, FactoryConfigurationError, SaxonApiException {
        // compute current date in format yyy-MM-dd
        LocalDate currentDate = LocalDate.now();
        DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd");
        
        // define default output stream
        File outputFile = new File(String.format("graph_%s.gexf", currentDate.format(formatter)));
        OutputStream out = new FileOutputStream(outputFile);

        // call exportGexf with default output stream
        this.exportGexf(out);
    }

    /**
     * Exports the graph to a GEXF file using a custom output stream.
     * 
     * @param out the output stream to which the graph is exported
     * @throws IOException if an I/O error occurs
     * @throws XMLStreamException if an error occurs while processing the XML
     * @throws FactoryConfigurationError if a configuration error occurs
     * @throws SaxonApiException if an error occurs while using the Saxon API
     */
    @SuppressWarnings("unchecked") // cast from CustomGraph<V,E> to CustomGraph<CustomVertex,CustomEdge> is checked
    public void exportGexf(OutputStream out) throws IOException, XMLStreamException, FactoryConfigurationError, SaxonApiException {
        // Export the graph to a GEXF file using the GephiExporter
        CustomGEXFExporter<CustomVertex, CustomEdge> exporter = new CustomGEXFExporter<>();
        exporter.setParameter(Parameter.EXPORT_META, true);
        
        // initialize saxon XML Processor to use correct indentation and formatting
        Processor p = new net.sf.saxon.s9api.Processor();
        Serializer s = p.newSerializer();
        s.setOutputProperty(Property.METHOD, "xml");
        s.setOutputProperty(Property.INDENT, "yes");
        s.setOutputStream(out);
        XMLStreamWriter writer = s.getXMLStreamWriter();

        // export graph as XML compatible with the tool Gephi
        exporter.exportGraph((CustomGraph<CustomVertex, CustomEdge>) this, writer);
        writer.close();
    }

    /**
     * Exports the graph to a JSON file with a default filename based on the current date.
     *
     * @throws IOException if an I/O error occurs
     */
    public void exportJson() throws IOException {
        LocalDate currentDate = LocalDate.now();
        DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd");
        File outputFile = new File(String.format("graph_%s.json", currentDate.format(formatter)));
        try (OutputStream out = new FileOutputStream(outputFile)) {
            this.exportJson(out);
        }
    }

    /**
     * Exports the full graph as a single JSON document with two arrays:
     * <ul>
     *     <li>{@code vertices}: {@code id, lat, lon, alt}</li>
     *     <li>{@code edges}: {@code source, target, distance, slope, highway}</li>
     * </ul>
     * The document streams row-by-row and never buffers the full text in memory,
     * so it can safely be piped to disk or an HTTP response for large graphs.
     *
     * @param out the output stream to which the graph is exported
     * @throws IOException if an I/O error occurs
     */
    public void exportJson(OutputStream out) throws IOException {
        PrintWriter w = new PrintWriter(new OutputStreamWriter(out, StandardCharsets.UTF_8));
        try {
            w.print("{\n  \"vertices\": [\n");
            boolean first = true;
            for (V v : this.vertexSet()) {
                CustomVertex cv = (CustomVertex) v;
                JSONObject o = new JSONObject();
                o.put("id", cv.getOsmId());
                o.put("lat", cv.getLat());
                o.put("lon", cv.getLon());
                o.put("alt", cv.getAltitude());
                if (!first) w.print(",\n");
                first = false;
                w.print("    ");
                w.print(o.toJSONString());
            }
            w.print("\n  ],\n  \"edges\": [\n");
            first = true;
            for (E e : this.edgeSet()) {
                CustomEdge ce = (CustomEdge) e;
                JSONObject o = new JSONObject();
                o.put("source", ce.getSourceVertex().getOsmId());
                o.put("target", ce.getTargetVertex().getOsmId());
                o.put("distance", ce.getDistance());
                o.put("slope", ce.getSlope());
                o.put("highway", ce.getHighway());
                if (!first) w.print(",\n");
                first = false;
                w.print("    ");
                w.print(o.toJSONString());
            }
            w.print("\n  ]\n}\n");
            w.flush();
        } finally {
            // caller owns the underlying stream (e.g. HTTP response) — do not close here
        }
    }

    /**
     * Prunes the graph to retain only the nodes belonging to its largest connected component.
     * This method operates in several steps:
     * <ol>
     *     <li>Identify all connected components within the graph.</li>
     *     <li>Determine the largest connected component based on the number of nodes.</li>
     *     <li>Remove all nodes (and associated edges) not belonging to the largest connected component.</li>
     * </ol>
     * After execution, the graph will only contain nodes and edges that are part of the largest connected component.
     * This method can significantly alter the graph structure and should be used with caution.
     *
     * @throws RuntimeException If no connected components can be found in the graph, indicating an empty or improperly initialized graph.
     */
    public void prune() {
        // Step 1: Identify connected components
        ConnectivityInspector<V, E> connectivityInspector = new ConnectivityInspector<>(this);
        List<Set<V>> connectedComponents = connectivityInspector.connectedSets();

        // Step 2: Find the largest connected component
        Set<V> largestComponent = connectedComponents.stream()
                .max(Comparator.comparingInt(Set::size))
                .orElseThrow(() -> new RuntimeException("No connected components found"));

        // Step 3: Remove nodes not in the largest connected component
        for (V vertex : new ArrayList<>(this.vertexSet())) { // Avoid ConcurrentModificationException
            if (!largestComponent.contains(vertex)) {
                this.removeVertex(vertex);
            }
        }

        // At this point, graph contains only nodes from the largest connected component
        Routify.logger.info("Graph pruned to largest connected component");
    }

    public void mergeVertices(V v1, V v2) throws Exception {
        // Assuming v1 and v2 are the nodes you want to merge
        // Redirect edges from v1 to v2 and delete v1

        for (E edge : new HashSet<>(this.edgesOf(v1))) {
            V source = this.getEdgeSource(edge);
            V target = this.getEdgeTarget(edge);
            
            if (source.equals(v1)) {
                this.addEdge(v2, target);
            } else {
                this.addEdge(source, v2);
            }
            
            this.removeEdge(edge);
        }

        this.removeVertex(v1);

        throw new Exception("MERGED_VERTICES");
    }
}
