package ch.routify.graph;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.Map;

import javax.xml.stream.XMLStreamException;
import javax.xml.stream.XMLStreamWriter;

import org.jgrapht.nio.gexf.GEXFExporter;

import ch.routify.Routify;
import net.minidev.json.JSONObject;

/**
 * This generic class extends GEXFExporter<V, E> to be able to use the 'http://gexf.net/1.3/gexf.xsd' namespace
 * @author aeggerth@ethz.ch
 * @version 1.0
 */
public class CustomGEXFExporter<V, E> extends GEXFExporter<V, E> {

    public CustomGEXFExporter() {
        super();
    }

    public static double mapValue(double x, double in_min, double in_max, double out_min, double out_max) {
        return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min;
    }

    /**
     * exports generic JGraphT graphs as .gexf to import into Gephi
     * @param customGraph
     * @param out
     */
    public void exportGraph(CustomGraph<V, E> customGraph, XMLStreamWriter out) {
        try {
            // initialize color coding
            HashMap<String, Double> weightsWalk = new HashMap<>();
            HashMap<String, Double> weightsBike = new HashMap<>();
            HashMap<String, Double> weightsDrive = new HashMap<>();
            
            for (Map.Entry<String, Object> entry : Routify.sys.config_features.entrySet()) {
                String key = entry.getKey();
                JSONObject value = (JSONObject) entry.getValue();
                JSONObject modifiers = (JSONObject) value.get("weight_modifiers");

                double walk = (modifiers.containsKey("walk")) ? (double) modifiers.get("walk") : -1.0;
                double bike = (modifiers.containsKey("bike")) ? (double) modifiers.get("bike") : -1.0;
                double drive = (modifiers.containsKey("drive")) ? (double) modifiers.get("drive") : -1.0;

                weightsWalk.put(key, walk);
                weightsBike.put(key, bike);
                weightsDrive.put(key, drive);
            }

            double maxPenaltyWalk = customGraph.edgeSet().stream().mapToDouble((edge) -> {
                JSONObject weight_modifiers = (JSONObject) ((JSONObject) Routify.sys.config_features.get(((CustomEdge) edge).getHighway())).get("weight_modifiers");
                return (weight_modifiers.keySet().contains("walk")) ? ((double) weight_modifiers.get("walk")) : 1.0;
            }).max().getAsDouble();

            double maxPenaltyBike = customGraph.edgeSet().stream().mapToDouble((edge) -> {
                JSONObject weight_modifiers = (JSONObject) ((JSONObject) Routify.sys.config_features.get(((CustomEdge) edge).getHighway())).get("weight_modifiers");
                return (weight_modifiers.keySet().contains("bike")) ? ((double) weight_modifiers.get("bike")) : 1.0;
            }).max().getAsDouble();

            double maxPenaltyDrive = customGraph.edgeSet().stream().mapToDouble((edge) -> {
                JSONObject weight_modifiers = (JSONObject) ((JSONObject) Routify.sys.config_features.get(((CustomEdge) edge).getHighway())).get("weight_modifiers");
                return (weight_modifiers.keySet().contains("drive")) ? ((double) weight_modifiers.get("drive")) : 1.0;
            }).max().getAsDouble();

            Routify.logger.debug("Max penalties - Walk: {}, Bike: {}, Drive: {}", maxPenaltyWalk, maxPenaltyBike, maxPenaltyDrive);


            out.writeStartDocument();
            out.writeStartElement("gexf");

            // gexf configuration elements
            out.writeAttribute("xmlns", "http://gexf.net/1.3");
            out.writeAttribute("xmlns:viz", "http://gexf.net/1.3/viz");
            out.writeAttribute("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance");
            out.writeAttribute("xsi:schemaLocation", "http://gexf.net/1.3 http://gexf.net/1.3/gexf.xsd");
            out.writeAttribute("version", "1.3");

            // compute current date in format yyy-MM-dd
            LocalDate currentDate = LocalDate.now();
            DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd");
        
            // meta data
            out.writeStartElement("meta");
            out.writeAttribute("lastmodifieddate", currentDate.format(formatter));
            out.writeEndElement();
            
            // graph configuration
            out.writeStartElement("graph");
            out.writeAttribute("mode", "static");
            out.writeAttribute("defaultedgetype", "directed");

            // nodes
            out.writeStartElement("nodes");

            for (V v : customGraph.vertexSet()) {
                CustomVertex c = (CustomVertex) v;
                out.writeStartElement("node");

                    out.writeAttribute("id", c.getOsmId().toString());
                    out.writeAttribute("label", c.getOsmId().toString());

                    out.writeStartElement("viz:position");
                        out.writeAttribute("x", Double.toString(c.getLon()));
                        out.writeAttribute("y", Double.toString(c.getLat()));
                        out.writeAttribute("z", Double.toString(0));
                    out.writeEndElement();

                    out.writeStartElement("viz:size");
                        out.writeAttribute("value", "0.0000000001");
                    out.writeEndElement();

                    out.writeStartElement("viz:shape");
                        out.writeAttribute("value", "disc");
                    out.writeEndElement();

                out.writeEndElement();
            }

            // end nodes
            out.writeEndElement();

            // edges
            out.writeStartElement("edges");
            
            for (E edge : customGraph.edgeSet()) {
                CustomEdge e = (CustomEdge) edge;
                out.writeStartElement("edge");

                    // out.writeAttribute("id", e.getOsmId().toString());
                    out.writeAttribute("source", e.getSourceVertex().getOsmId().toString());
                    out.writeAttribute("target", e.getTargetVertex().getOsmId().toString());
                    out.writeAttribute("weight", Double.toString(1));

                    /*
                     * red      -> walk
                     * green    -> bike
                     * blue     -> drive
                     */

                    double valueWalk = weightsWalk.get(((CustomEdge) edge).getHighway());
                    double valueBike = weightsBike.get(((CustomEdge) edge).getHighway());
                    double valueDrive = weightsDrive.get(((CustomEdge) edge).getHighway());

                    double scaledWalk = mapValue(valueWalk, 1, 50, 1, 100) / 100;
                    double scaledBike = mapValue(valueBike, 1, 10, 1, 100) / 100;
                    double scaledDrive = mapValue(valueDrive, 1, 2.5, 1, 100) / 100;

                    out.writeStartElement("viz:color");
                        out.writeAttribute("r", (scaledWalk >= 0.0) ? Integer.toString((int) (255 * (1 - scaledWalk))) : Integer.toString(0));
                        out.writeAttribute("g", (scaledBike >= 0.0) ? Integer.toString((int) (255 * (1 - scaledBike))) : Integer.toString(0));
                        out.writeAttribute("b", (scaledDrive >= 0.0) ? Integer.toString((int) (255 * (1 - scaledDrive))) : Integer.toString(0));
                        // out.writeAttribute("r", Integer.toString(0));
                        // out.writeAttribute("g", Integer.toString(0));
                        // out.writeAttribute("b", Integer.toString(255));
                    out.writeEndElement();

                    out.writeStartElement("viz:shape");
                        out.writeAttribute("value", "solid");
                    out.writeEndElement();

                out.writeEndElement();
            }

            // end edges
            out.writeEndElement();
            // end graph
            out.writeEndElement();
            // end gexf
            out.writeEndElement();

            out.writeEndDocument();
            out.flush();
        } catch (XMLStreamException e) {
            Routify.logger.error("Error writing GEXF file", e);
        }

    }
}
