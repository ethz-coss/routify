package ch.routify.routing.config;

import java.util.List;

import ch.routify.routing.operations.WeightOperation;

/**
 * Immutable representation of a routing mode pipeline.
 */
public class RoutingModeDefinition {

    private final String name;
    private final List<WeightOperation> operations;

    public RoutingModeDefinition(String name, List<WeightOperation> operations) {
        this.name = name;
        this.operations = operations;
    }

    public String getName() {
        return name;
    }

    public List<WeightOperation> getOperations() {
        return operations;
    }
}
