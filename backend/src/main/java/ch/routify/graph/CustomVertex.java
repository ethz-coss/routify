package ch.routify.graph;

import org.apache.commons.lang.builder.EqualsBuilder;
import ch.routify.Routify;

import lombok.Getter;
import lombok.Setter;

import java.util.HashMap;

/**
 * Represents a custom vertex in a graph, uniquely identified by a UUID and an OpenStreetMap ID (osmId).
 * Each vertex is characterized by geographical coordinates (latitude, longitude) and optionally altitude and noise level.
 * This class supports determining if a vertex represents a tunnel or a bridge and includes utility methods for geographical calculations.
 * <p>
 * The primary coordinate system used is EPSG:4326 (WGS 84).
 * </p>
 *
 * @author Alexander Eggerth
 * @version 1.0
 * @since 2025-02-05 (distance calculation switched from the spherical law of cosines to the Haversine formula by Sachit Mahajan)
 */
public class CustomVertex {
    @Getter
    private final double latitude, longitude;
    @Getter
    private final Long osmId;
    // sentinel value -1 to filter uninitialized values
    @Getter
    private double altitude, noise;
    @Getter @Setter
    private double pm10;
    @Getter
    private long id;

    private static HashMap<Long, CustomVertex> node_id_map = new HashMap<>();
        
    /**
     * Constructs a CustomVertex with specified geographical coordinates, tunnel and bridge status, and an OpenStreetMap ID.
     * Altitude and noise level are retrieved from the Routify system if available; otherwise, they are initialized to sentinel values.
     *
     * @param latitude  The latitude of the vertex in decimal degrees.
     * @param longitude The longitude of the vertex in decimal degrees.
     * @param osmId     The OpenStreetMap ID associated with the vertex.
     */
    public CustomVertex(double latitude, double longitude, Long osmId) {
        this.osmId = osmId;
        this.latitude = latitude;
        this.longitude = longitude;
        this.id = this.computeId();
        node_id_map.put(this.computeId(), this);
        this.loadMetaData();        
    }


    public static CustomVertex getByNodeId(long nodeId) {
        return node_id_map.get(nodeId);
    }

    public void loadMetaData() {
        try {
            this.altitude = (double) Routify.sys.getAltData().get(Long.toString(osmId));
        } catch(Exception e) {
        }

        try {
            this.noise = (double) Routify.sys.getNoiseData().get(Long.toString(osmId));
        } catch(Exception e) {
        }
    }

    public void setAltitude(double altitude) {
        this.altitude = altitude;
    }

    /**
     * Returns a string representation of the vertex in the format "(latitude,longitude)".
     *
     * @return A string representing the vertex coordinates.
     */
    @Override
    public String toString() {
        return String.format("(%s,%s)", latitude, longitude);
    }

    /**
     * Converts the CustomVertex to a double array containing the latitude and longitude.
     * This format is compatible with the "coordinates" array in a GeoJSON "LineString" object.
     *
     * @return An array of doubles [latitude, longitude] in EPSG:4326 format.
     */
    public double[] toLineStringArray() {
        return new double[] {this.latitude, this.longitude};
    }

    /**
     * Converts the CustomVertex to a double array containing the longitude and latitude.
     * This format is often used in geographic systems, where the order is [longitude, latitude].
     * It is compatible with coordinate formats used by many map APIs and geographic data systems.
     *
     * @return An array of doubles [longitude, latitude] in EPSG:4326 format.
     */
    public double[] toLonLatArray() {
        return new double[] {this.longitude, this.latitude};
    }

    // Getters for the class properties

    public Long getOsmId() {
        return osmId;
    }
    
    public double getLon() {
        return longitude;
    }
     
    public double getLat() {
        return latitude;
    }

    public double getAltitude() {
        return altitude;
    }

    public double getNoise() {
        return noise;
    }

    /**
     * Calculates the distance in meters between two CustomVertex instances using the Haversine formula.
     * This method considers the earth's curvature and is appropriate for short distances.
     *
     * @param from The starting CustomVertex.
     * @param to   The ending CustomVertex.
     * @return The distance between the two vertices in meters.
     */
    public static double distance(CustomVertex from, CustomVertex to) {
        final double EARTH_RADIUS_KM = 6371.0088; // Earth's mean radius in kilometers

        double lat1 = Math.toRadians(from.getLat());
        double lon1 = Math.toRadians(from.getLon());
        double lat2 = Math.toRadians(to.getLat());
        double lon2 = Math.toRadians(to.getLon());

        if (lat1 == lat2 && lon1 == lon2) {
            return 0;
        } else {
            double dLat = lat2 - lat1;
            double dLon = lon2 - lon1;
            double a = Math.pow(Math.sin(dLat / 2), 2)
                     + Math.cos(lat1) * Math.cos(lat2) * Math.pow(Math.sin(dLon / 2), 2);
            double c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
            double dist = EARTH_RADIUS_KM * c;
            return dist * 1000; // Convert km to meters
        }
    }
    
    
    /**
     * Compares this CustomVertex with another object for equality, based on latitude and longitude.
     *
     * @param compareTo The object to compare with.
     * @return true if the specified object is a CustomVertex with the same latitude and longitude.
     */
    @Override   
    public boolean equals(Object compareTo) {
        if (compareTo instanceof CustomVertex) {
            CustomVertex otherCoord = (CustomVertex) compareTo;
            EqualsBuilder builder = new EqualsBuilder();
            builder.append(this.longitude, otherCoord.getLon());
            builder.append(this.latitude, otherCoord.getLat());
            return builder.isEquals();
        }
        return false;
    }

    /**
     * Generates a strong hash code for this CustomVertex based on its coordinates and OSM ID.
     * Uses a combination of bit manipulation and prime number multiplication for better distribution.
     *
     * @return A hash code value for this object.
     */
    @Override
    public int hashCode() {
        // Convert coordinates to integers for better hash distribution
        // Multiply by a large factor to preserve precision and avoid collisions
        int latHash = (int) (this.latitude * 1000000);
        int lonHash = (int) (this.longitude * 1000000);
        
        // Use prime numbers for better distribution
        final int prime1 = 31;
        final int prime2 = 17;
        final int prime3 = 13;
        
        int result = prime1;
        result = result * prime2 + latHash;
        result = result * prime3 + lonHash;
        result = result * prime1 + (this.osmId != null ? this.osmId.hashCode() : 0);
        
        // Additional mixing for better distribution
        result = result ^ (result >>> 16);
        result = result * 0x85ebca6b;
        result = result ^ (result >>> 13);
        result = result * 0xc2b2ae35;
        result = result ^ (result >>> 16);
        
        return result;
    }

    /**
     * Computes a deterministic id using the full range of a long value.
     * This provides maximum uniqueness and distribution for the coordinates and OSM ID.
     *
     * @return An id using the full 64-bit range.
     */
    public long computeId() {
        // Convert coordinates to long values with high precision
        long latBits = Double.doubleToLongBits(this.latitude);
        long lonBits = Double.doubleToLongBits(this.longitude);
        
        // Use a deterministic mixing function for the full long range
        long hash = 0x9e3779b97f4a7c15L; // Golden ratio for 64-bit
        
        // Mix latitude bits
        hash = hash ^ latBits;
        hash = hash * 0xbf58476d1ce4e5b9L; // Prime multiplier
        hash = hash ^ (hash >>> 32);
        
        // Mix longitude bits
        hash = hash ^ lonBits;
        hash = hash * 0x94d049bb133111ebL; // Another prime multiplier
        hash = hash ^ (hash >>> 32);
        
        // Mix OSM ID
        long osmHash = this.osmId != null ? this.osmId : 0L;
        hash = hash ^ osmHash;
        hash = hash * 0x9e3779b97f4a7c15L;
        hash = hash ^ (hash >>> 32);
        
        // Final mixing
        hash = hash ^ (hash >>> 33);
        hash = hash * 0xff51afd7ed558ccdL;
        hash = hash ^ (hash >>> 33);
        hash = hash * 0xc4ceb9fe1a85ec53L;
        hash = hash ^ (hash >>> 33);
        
        return hash;
    }

    // Manual getter methods (Lombok not working properly)
    public double getPm10() {
        return pm10;
    }
    
    public void setPm10(double pm10) {
        this.pm10 = pm10;
    }
    
    public long getId() {
        return id;
    }
}
