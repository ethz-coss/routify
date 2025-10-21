package ch.routify.routing;

import java.util.ArrayList;

import ch.routify.bearingcalculator.BearingCalculator;
import ch.routify.graph.CustomEdge;
import lombok.Getter;

@Getter
public class DirectionSegment {
    public ArrayList<Long> edges = new ArrayList<Long>();
    public double distance = 0;
    public String cardinalDirection = "";
    public String name;
    public String osmId;

    public DirectionSegment(CustomEdge e) {
        this.edges.add(e.getId());
        distance = e.getDistance();
        cardinalDirection = BearingCalculator.getCardinalDirection(e.getBearing());
        name = e.getTag("name");
        if(name == null) name = "";
        osmId = e.getOsmId().toString();
    }

    public void addEdge(CustomEdge e) {
        edges.add(e.getId());
        distance += e.getDistance();
    }
}
