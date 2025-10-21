package ch.routify.graph;

import java.util.HashMap;
import java.util.Map;

/**
 * A factory class for creating and managing {@link CustomVertex} objects to ensure that only unique vertices
 * are maintained in memory. This implementation uses a caching mechanism to avoid creating multiple objects
 * with the same properties.
 * 
 * @author aeggerth@ethz.ch
 * @version 1.0
 */
public class CustomVertexFactory {
    /**
     * Cache for storing and reusing {@link CustomVertex} instances based on their hash codes to ensure uniqueness.
     */
    private Map<Long, CustomVertex> objectCache = new HashMap<>();

    /**
     * Creates a {@link CustomVertex} object or retrieves an existing one from the cache with the same properties.
     * 
     * @param latitude The latitude of the vertex.
     * @param longitude The longitude of the vertex.
     * @param isTunnel Flag indicating whether the vertex is part of a tunnel.
     * @param isBridge Flag indicating whether the vertex is part of a bridge.
     * @param osmId The OpenStreetMap identifier for the vertex.
     * @return A {@link CustomVertex} instance with the specified properties. If an instance with the same properties
     *         already exists, it is returned instead of creating a new one.
     */
    public CustomVertex createObject(double latitude, double longitude, Long osmId) {
        CustomVertex newObj = new CustomVertex(latitude, longitude, osmId);

        if(objectCache.containsKey(newObj.computeId())) {
            // If an object with the same property already exists, return it.
            return objectCache.get(newObj.computeId());
        } else {
            // Otherwise, store the new object in the cache and return it.
            objectCache.put(newObj.computeId(), newObj);
            return newObj;
        }
    }
}
