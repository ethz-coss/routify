package ch.routify.graph;

import java.util.HashMap;
import java.util.Set;
import org.apache.commons.lang.builder.HashCodeBuilder;
import org.jgrapht.graph.DefaultWeightedEdge;

import ch.routify.Routify;
import ch.routify.bearingcalculator.BearingCalculator;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.Setter;
import lombok.ToString;
import net.minidev.json.JSONObject;

/**
 * CustomEdge extends the DefaultWeightedEdge class to model edges in a graph with additional attributes specific to mapping applications.
 * It includes information such as elevation, distance, noise level, and attributes for bridges, tunnels, and types of roads.
 * Additionally, it calculates travel times for different modes of transport.
 * 
 * @author Alexander Eggerth
 * @since 2025-02-05 (Updated for realistic default speed by Sachit Mahajan)
 * @version 1.1
 */
@Getter
@Setter
public class CustomEdge extends DefaultWeightedEdge {
    @Getter
    private int hashCode;

    // assign unique id to edge to be able to distinguish between different edges with same osmId (way/id)
    private static HashMap<Long, CustomEdge> hashToCustomEdge = new HashMap<>();
    
    // Attributes specific to the edge
    private final Long osmId;
    private final CustomVertex source, target;
    private final JSONObject tags;
    @Getter
    public final long id;

    // sentinel value -1 to filter uninitialized values
    @Getter
    private double slope = -1, distance = -1, noise = -1, greenIndex = -1, aqius = -1;
    @Getter
    private double maxspeed;

    // additional meta data
    @Getter
    public String highway;

    // bearing for directions
    @Getter
    public double bearing;
    @Getter
    public String cardinalDirection;

    public static double avgPm10 = 0.0;
    public static double maxPm10 = 0.0;
    public static double minPm10 = Double.MAX_VALUE;

    // travel time for different transport modes
    private HashMap<String, Double> traveltime = new HashMap<>();

    public CustomEdge(CustomVertex source, CustomVertex target, JSONObject tags, Long osmId) throws Exception {
        super();

        
        // osm features (e.g. a street) can be composed out of multiple segments but all segments are represented
        // by the same osm id, so we need to add another unique identifier to distinguish between this segments
        
        this.source = source;
        this.target = target;
        this.tags = tags;
        this.osmId = osmId;
        
        // Compute ID after source and target are set
        this.id = this.computeId();
        hashToCustomEdge.put(this.id, this);
        
        // noise data is only definded for vertices, we assign linear average value to edge
        this.noise = (source.getNoise() + target.getNoise()) / 2;
        
        this.distance = CustomVertex.distance(source, target);
        
        HashCodeBuilder builder = new HashCodeBuilder();
        builder.append(this.source.getOsmId());
        builder.append(this.target.getOsmId());
        builder.append(this.osmId);
        this.hashCode = builder.toHashCode();
        
        // check distance == 0 (zero division) and calculate slope 
        this.calculateSlope();

        // add tag highway to object, because we use lombok to render object to serializer (automatic serializing of response objects)
        this.highway = this.getTag("highway");
        
        // CHANGED: Set maxspeed in km/h using a more realistic default.
        try {
            String maxspeedTag = this.getTag("maxspeed");
            if (maxspeedTag == null || maxspeedTag.isEmpty()) {
                throw new Exception("No maxspeed tag");
            }
            // Additional parsing could be added here for non-numeric or unit-specified values.
            this.maxspeed = Double.valueOf(maxspeedTag);
        } catch (Exception e) {
            // CHANGED: Use fallback default based on highway type if available.
            if (this.highway != null) {
                switch (this.highway) {
                    case "motorway":
                        this.maxspeed = 120.0;
                        break;
                    case "trunk":
                        this.maxspeed = 100.0;
                        break;
                    case "primary":
                        this.maxspeed = 80.0;
                        break;
                    case "secondary":
                        this.maxspeed = 60.0;
                        break;
                    case "residential":
                        this.maxspeed = 50.0;
                        break;
                    default:
                        this.maxspeed = 50.0;
                        break;
                }
            } else {
                // CHANGED: Fallback if highway type is also unavailable.
                this.maxspeed = 50.0;
            }
        }
        this.setTraveltime();

        // get green inedx and aqius from cached meta data
        this.loadMetaData();

        // calculate bearing
        this.bearing = BearingCalculator.calculateBearing(source.getLat(), source.getLon(), target.getLat(), target.getLon());

        // calculate cardinal direction
        this.cardinalDirection = BearingCalculator.getCardinalDirection(this.bearing);
    }


    /**
     * Inspects cached meta data and checks for values associated with the edgs osm id
     * depends on CossMapsSystem
     */
    public void loadMetaData() {
        try {
            this.greenIndex = (double) Routify.sys.getGreenIndexData().get(Long.toString(osmId));
        } catch(Exception e) {
        }

        // AQI values are fetched dynamically; no file-based cache
    }

    private double calculateSlope() {
        if(this.distance == 0) return 0.0;
        this.slope = (target.getAltitude() - source.getAltitude()) / distance;
        return this.slope;
    }

    /**
     * Sets the altitude value of the source vertex and target vertex to the average value of the direct neighbours
     * and recomputes slope, this is necessary because outliers can be reduced.
     */
    public void correctAltitude() {
        setAverageAltitude(this.getSourceVertex());
        setAverageAltitude(this.getTargetVertex());
        calculateSlope();
    }

    private void setAverageAltitude(CustomVertex v) {
        Set<CustomEdge> outgoing = Routify.sys.getGraph().outgoingEdgesOf(v);
        Set<CustomEdge> incoming = Routify.sys.getGraph().incomingEdgesOf(v);

        if(outgoing.size() < 1 && incoming.size() < 1) return;

        double min = Double.MAX_VALUE;
        for(CustomEdge e : outgoing) {
            min = Math.min(min, e.getTargetVertex().getAltitude());
        }
        for(CustomEdge e : incoming) {
            min = Math.min(min, e.getTargetVertex().getAltitude());
        }

        v.setAltitude((min + v.getAltitude()) / 2);
    }

    private void setTraveltime() {
        // assume average speed of 15 km/h for bike and 5 km/h for pedestrian
        this.traveltime.put("transport_mode_drive", ((this.distance / 1000) / this.maxspeed) * 60);
        this.traveltime.put("transport_mode_cycle", ((this.distance / 1000) / 15.0) * 60);
        this.traveltime.put("transport_mode_walk",  ((this.distance / 1000) / 5.0) * 60);
    }

    public String getTag(String tag) {
        try {
            return (String) tags.get(tag);
        } catch(Exception e) {
            Routify.logger.error(String.format("unknown tag %s at edge with osmId=%d", tag, this.osmId), e);
        }
        return null;
    }

    public CustomVertex getSourceVertex() {
        return this.source;
    }

    public CustomVertex getTargetVertex() {
        return this.target;
    }

    public double getEdgeWeight() {
        return this.getWeight();
    }

    public double getTravelTime(String transportMode) {
        return this.traveltime.get(transportMode);
    }

    /**
     * Gets travel time for a specific transport mode, or null if travel time is disabled.
     * This method is used for conditional serialization.
     * 
     * @param transportMode The transport mode to get travel time for.
     * @param includeTraveltime Whether to include travel time in the response.
     * @return Travel time in minutes, or null if travel time is disabled.
     */
    public Double getTravelTime(String transportMode, boolean includeTraveltime) {
        if (!includeTraveltime) {
            return null;
        }
        return this.traveltime.get(transportMode);
    }

    /**
     * Gets the travel time map, or null if travel time is disabled.
     * This method is used for conditional serialization.
     * 
     * @param includeTraveltime Whether to include travel time in the response.
     * @return Travel time map, or null if travel time is disabled.
     */
    public HashMap<String, Double> getTraveltime(boolean includeTraveltime) {
        if (!includeTraveltime) {
            return null;
        }
        return this.traveltime;
    }

    public void setAqius(double aqius) {
        this.aqius = aqius;
    }

    @ToString.Include(name = "pm_10")
    @EqualsAndHashCode.Include
    public double getPm_10() {
        return (this.source.getPm10() + this.target.getPm10()) / 2;
    }

    /**
     * Computes an id based on the long hash codes of source and target vertices.
     * This provides a unique identifier for edges based on their endpoints.
     * 
     * @return id for this edge
     */
    private long computeId() {
        // Use a prime number for better hash distribution
        final long prime = 31L;
        long result = 1L;
        
        // Include source vertex long hash code
        result = prime * result + source.getId();
        
        // Include target vertex long hash code
        result = prime * result + target.getId();
        
        // Include OSM ID for additional uniqueness
        result = prime * result + (osmId != null ? osmId : 0L);
        
        return result;
    }

    /**
     * Returns {@link CustomEdge} associated with the provided id
     * @param id the id to look up
     * @return the CustomEdge associated with the id, or null if not found
     */
    public static CustomEdge getById(long id) {
        return hashToCustomEdge.get(id);
    }

    // Manual getter methods (Lombok not working properly)
    public JSONObject getTags() {
        return tags;
    }
    
    public Long getOsmId() {
        return osmId;
    }
    
    public long getId() {
        return id;
    }
    
    public double getDistance() {
        return distance;
    }
    
    public double getSlope() {
        return slope;
    }
    
    public double getNoise() {
        return noise;
    }
    
    public double getGreenIndex() {
        return greenIndex;
    }
    
    public double getAqius() {
        return aqius;
    }
    
    public String getHighway() {
        return highway;
    }
    
    public double getMaxspeed() {
        return maxspeed;
    }
    
    public double getBearing() {
        return bearing;
    }
    
    public String getCardinalDirection() {
        return cardinalDirection;
    }
}
