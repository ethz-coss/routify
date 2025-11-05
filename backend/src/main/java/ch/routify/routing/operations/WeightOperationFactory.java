package ch.routify.routing.operations;

import java.util.Locale;
import java.util.Map;

/**
 * Creates weight operations based on configuration identifiers.
 */
public final class WeightOperationFactory {

    private WeightOperationFactory() {
    }

    public static WeightOperation create(String identifier, Map<String, Object> params) {
        String key = identifier == null ? "" : identifier.toLowerCase(Locale.ROOT);

        switch (key) {
            case "base":
                return new BaseWeightsOperation();
            case "filter-disallowed":
                return new FilterDisallowedOperation();
            case "slope":
                return new SlopeOperation(params);
            case "green-index":
                return new GreenIndexOperation(params);
            case "noise":
                return new NoiseOperation(params);
            case "air":
                return new AirOperation(params);
            default:
                throw new IllegalArgumentException("Unknown weight operation identifier: " + identifier);
        }
    }
}
