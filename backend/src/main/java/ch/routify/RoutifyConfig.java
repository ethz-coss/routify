package ch.routify;

import lombok.Getter;

/**
 * Centralized configuration for Routify resource file paths.
 * These are the default, un-extended paths. Runtime code can adapt them
 * (e.g., via CossMapsSystem.extendedPath) depending on the environment.
 */
@Getter
public class RoutifyConfig {

    private final String pathToMap = "basemap_admin_level_8.json";
    private final String pathConfFeatures = "config_features.json";
    private final String pathAltitude = "altitude_admin_level_8.json";
    private final String pathGreenIndex = "green_index_admin_level_8.json";
    private final String pathNoise = "noise_admin_level_8.json";
    private final String pathToBoundary = "boundary_admin_level_8.geojson";
    
    // Allowed feature sets per transport mode
    private final String[] allowedFeaturesWalk = {
        "construction", "platform", "bus_stop", "bridleway", "steps", "pedestrian", "footway", "path",
        "service", "road", "residential", "living_street", "corridor", "elevator"
    };

    private final String[] allowedFeaturesBike = {
        "bus_stop", "bridleway", "cycleway", "pedestrian", "footway", "path", "track", "service", "road",
        "residential", "tertiary", "tertiary_link", "living_street", "construction", "secondary", "secondary_link",
        "corridor", "elevator"
    };

    private final String[] allowedFeaturesDrive = {
        "motorway", "motorway_link", "residential", "primary", "primary_link", "secondary", "service",
        "road", "secondary_link", "tertiary", "tertiary_link", "trunk", "trunk_link", "living_street"
    };

    // Manual getter methods (Lombok not working properly)
    public String getPathToMap() {
        return pathToMap;
    }
    
    public String getPathConfFeatures() {
        return pathConfFeatures;
    }
    
    public String getPathAltitude() {
        return pathAltitude;
    }
    
    public String getPathGreenIndex() {
        return pathGreenIndex;
    }
    
    public String getPathNoise() {
        return pathNoise;
    }
    
    public String getPathToBoundary() {
        return pathToBoundary;
    }
    
    public String[] getAllowedFeaturesWalk() {
        return allowedFeaturesWalk;
    }
    
    public String[] getAllowedFeaturesBike() {
        return allowedFeaturesBike;
    }
    
    public String[] getAllowedFeaturesDrive() {
        return allowedFeaturesDrive;
    }
}


