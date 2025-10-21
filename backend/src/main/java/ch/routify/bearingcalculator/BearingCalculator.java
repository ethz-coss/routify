package ch.routify.bearingcalculator;

import ch.routify.Routify;

public class BearingCalculator {

    // Convert degrees to radians
    public static double toRadians(double degrees) {
        return Math.toRadians(degrees);
    }

    // Convert radians to degrees
    public static double toDegrees(double radians) {
        return Math.toDegrees(radians);
    }

    // Normalize bearing to 0-360 degrees
    public static double normalizeBearing(double bearing) {
        return (bearing + 360) % 360;
    }

    // Calculate the bearing between two points
    public static double calculateBearing(double startLat, double startLng, double endLat, double endLng) {
        double startLatRad = toRadians(startLat);
        double endLatRad = toRadians(endLat);
        double deltaLngRad = toRadians(endLng - startLng);

        double y = Math.sin(deltaLngRad) * Math.cos(endLatRad);
        double x = Math.cos(startLatRad) * Math.sin(endLatRad) -
                   Math.sin(startLatRad) * Math.cos(endLatRad) * Math.cos(deltaLngRad);

        double bearingRad = Math.atan2(y, x);
        double bearingDeg = toDegrees(bearingRad);

        return normalizeBearing(bearingDeg);
    }

    // Map bearing to cardinal direction
    public static String getCardinalDirection(double bearing) {
        String[] directions = {
            "North", "North-Northeast", "Northeast", "East-Northeast",
            "East", "East-Southeast", "Southeast", "South-Southeast",
            "South", "South-Southwest", "Southwest", "West-Southwest",
            "West", "West-Northwest", "Northwest", "North-Northwest", "North"
        };

        // Each direction occupies 22.5 degrees (360/16)
        int index = (int)Math.round(((bearing % 360) / 22.5));
        return directions[index];
    }

    public static void main(String[] args) {
        double startLat = 37.7749; // Example start latitude
        double startLng = -122.4194; // Example start longitude
        double endLat = 34.0522; // Example end latitude
        double endLng = -118.2437; // Example end longitude

        double bearing = calculateBearing(startLat, startLng, endLat, endLng);
        String cardinalDirection = getCardinalDirection(bearing);

        Routify.logger.debug("Bearing from start to end: {} degrees, cardinal direction: {}", bearing, cardinalDirection);
    }
}

