package ch.routify.routing;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.Set;

import ch.routify.graph.CustomEdge;
import ch.routify.graph.CustomVertex;

/**
 * Supplies weight modifications for edges in a graph based on various criteria such as slope, green index,
 * noise, air quality, and traffic. This class is designed to adjust the weights of edges for routing algorithms
 * to take into account environmental and physical factors.
 */
public class WeightSupplier {

    private Set<CustomEdge> edges;
    private HashMap<CustomEdge, Double> weights;

    /**
     * Constructs a new {@code WeightSupplier} with a set of edges and their corresponding weights.
     *
     * @param edges A set of {@code CustomEdge} objects representing the edges of a graph.
     * @param weights A {@code HashMap} mapping each edge to its initial weight.
     */
    public WeightSupplier(Set<CustomEdge> edges, HashMap<CustomEdge, Double> weights) {
        this.edges = edges;
        this.weights = weights;
    }

    /**
     * Modifies the weights of edges based on their slope, applying an impact factor to the calculation.
     *
     * @param maxSlope max slope wanted by the user. In range 0 ... 100
     * @return A {@code HashMap} of {@code CustomEdge} to modified weight values based on slope.
     */
    HashMap<CustomEdge, Double> slope(double input) {
        // double impact = input / 100;
        double limit = input / 100;
        HashMap<CustomEdge, Double> modifiedWeights = new HashMap<>();
        for(CustomEdge e : edges) {
            double tmpWeight = weights.get(e);

            try {
                double absSlope = Math.abs(e.getSlope());
                // tmpWeight += impact * (e.getDistance() * Math.exp(5 * (1 + absSlope)));
                if(e.getSlope() > limit) {
                    tmpWeight += 20 * e.getDistance() * (1 + absSlope);
                }
            } catch (Exception exception) {
                tmpWeight *= 10000;
            }

            modifiedWeights.put(e, tmpWeight);
        }
        return modifiedWeights;
    }

    /**
     * Modifies the weights of edges based on their green index, applying an impact factor to the calculation.
     *
     * @param impact The impact factor to apply to the green index weight modification.
     * @return A {@code HashMap} of {@code CustomEdge} to modified weight values based on green index.
     */
    HashMap<CustomEdge, Double> greenIndex(double impact) {
        double accelerate = 2.0;
        HashMap<CustomEdge, Double> modifiedWeights = new HashMap<>();
        for(CustomEdge e : edges) {
            double tmpWeight = weights.get(e);
            // exclude unclassified vertices
            if(e.getGreenIndex() >= 0 && e.getGreenIndex() <= 1.0) {
                tmpWeight = weights.get(e) + e.getDistance() * impact * accelerate * (1 - e.getGreenIndex()); // 1 - because higher green index is better
            } else {
                tmpWeight = 10000;
            }
            modifiedWeights.put(e, tmpWeight);
        }
        return modifiedWeights;
    }

    /**
     * Modifies the weights of edges based on their noise level, applying an impact factor to the calculation.
     *
     * @param impact The impact factor to apply to the noise level weight modification.
     * @return A {@code HashMap} of {@code CustomEdge} to modified weight values based on noise level.
     */
    HashMap<CustomEdge, Double> noise(double impact) {
        HashMap<CustomEdge, Double> modifiedWeights = new HashMap<>();
        double accelerate = 1.0;
        for(CustomEdge e : edges) {
            double tmpWeight = weights.get(e);
            // exclude unclassified vertices
            if(e.getNoise() >= 0) {
                tmpWeight = weights.get(e) + e.getDistance() * impact * accelerate * e.getNoise();
            } else {
                tmpWeight = 10000;
            }
            modifiedWeights.put(e, tmpWeight);
        }
        return modifiedWeights;
    }

    /**
     * Modifies the weights of edges based on air quality, applying an impact factor to the calculation.
     *
     * @param impact The impact factor to apply to the air quality weight modification.
     * @return A {@code HashMap} of {@code CustomEdge} to modified weight values based on air quality.
     */
    HashMap<CustomEdge, Double> air(double impact) {
        HashMap<CustomEdge, Double> modifiedWeights = new HashMap<>();
        double alpha = 20.0;
        for(CustomEdge e : edges) {
            double pm10 = e.getPm_10();
            double dist = e.getDistance();
            double tmpWeight = weights.get(e);
            // exclude unclassified vertices
            if(e.getPm_10() >= 0) {
                double exponent = Math.exp(pm10 - CustomEdge.minPm10); 
                tmpWeight = dist + alpha * exponent;
            } else {
                tmpWeight = 10000;
            }
            modifiedWeights.put(e, tmpWeight);
        }
        return modifiedWeights;
    }

    /**
     * Modifies the weights of edges considering their proximity to the specified path, primarily to factor in traffic.
     *
     * @param path An {@code ArrayList} of {@code CustomVertex} objects representing a path.
     * @return A {@code HashMap} of {@code CustomEdge} to modified weight values considering traffic.
     */
    HashMap<CustomEdge, Double> traffic(ArrayList<CustomVertex> path) {
        HashMap<CustomEdge, Double> modifiedWeights = new HashMap<>();
        for(CustomEdge e : edges) {
            double tmpWeight = weights.get(e);
            // exclude unclassified vertices
            if(path.contains(e.getSourceVertex()) || path.contains(e.getTargetVertex())) {
                tmpWeight = e.getDistance() * 0.5;
            } else {
                tmpWeight = weights.get(e) * 1000;
            }
            modifiedWeights.put(e, tmpWeight);
        }
        return modifiedWeights;
    }

    HashMap<CustomEdge, Double> feedbackCi(double impact) {
        HashMap<CustomEdge, Double> modifiedWeights = new HashMap<>();
        for(CustomEdge e : edges) {
            double tmpWeight = weights.get(e);
            tmpWeight += e.getDistance() * impact * (4 - e.getFeedbackCi());
            modifiedWeights.put(e, tmpWeight);
        }
        return modifiedWeights;
    }

    HashMap<CustomEdge, Double> feedbackTwa(double impact) {
        HashMap<CustomEdge, Double> modifiedWeights = new HashMap<>();
        for(CustomEdge e : edges) {
            double tmpWeight = weights.get(e);
            tmpWeight += e.getDistance() * impact * (4 - e.getFeedbackTwa());
            modifiedWeights.put(e, tmpWeight);
        }
        return modifiedWeights;
    }
    
}
