package ch.routify.routing.operations;

/**
 * Small helper for normalizing slider inputs and metric values to a [0, 1] range.
 */
final class NormalizationUtils {

    private static final double EPSILON = 1e-9;

    private NormalizationUtils() {
    }

    /**
     * Normalizes a percentage slider value (0–100) to [0, 1].
     */
    static double normalizeImpact(double rawValue) {
        if (Double.isNaN(rawValue)) {
            return 0.0;
        }
        return clamp(rawValue / 100.0, 0.0, 1.0);
    }

    /**
     * Normalizes a metric using its observed min/max bounds.
     */
    static double normalize(double value, double min, double max) {
        if (Double.isNaN(value)) {
            return 0.0;
        }
        if (max - min <= EPSILON) {
            return 0.0;
        }
        return clamp((value - min) / (max - min), 0.0, 1.0);
    }

    static double clamp(double value, double min, double max) {
        return Math.max(min, Math.min(max, value));
    }
}
