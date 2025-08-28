import * as L from 'leaflet';

export const icon_walk = L.icon({
    iconUrl: 'assets/icons/directions_walk.png',
    // shadowUrl: 'leaf-shadow.png',

    iconSize:     [30, 30], // size of the icon
    // shadowSize:   [50, 64], // size of the shadow
    // iconAnchor:   [60, 30], // point of the icon which will correspond to marker's location
    // shadowAnchor: [4, 62],  // the same for the shadow
    popupAnchor:  [0, 0] // point from which the popup should open relative to the iconAnchor
});

export const icon_bike = L.icon({
    iconUrl: 'assets/icons/directions_bike.png',
    iconSize:     [30, 30], // size of the icon
    popupAnchor:  [0, 0] // point from which the popup should open relative to the iconAnchor
});

export const icon_car = L.icon({
    iconUrl: 'assets/icons/directions_car.png',
    iconSize:     [30, 30], // size of the icon
    popupAnchor:  [0, 0] // point from which the popup should open relative to the iconAnchor
});

export const icon_a = L.icon({
    iconUrl: 'assets/icons/marker_a.png',
    iconSize:     [30, 30], // size of the icon
    popupAnchor:  [0, 0] // point from which the popup should open relative to the iconAnchor
});

export const icon_b = L.icon({
    iconUrl: 'assets/icons/marker_b.png',
    iconSize:     [30, 30], // size of the icon
    popupAnchor:  [0, 0] // point from which the popup should open relative to the iconAnchor
});

export function getIcon(transportMode: string): L.Icon {
    switch(transportMode) {
        case 'transport_mode_walk':
            return icon_walk;
        case 'transport_mode_cycle':
            return icon_bike;
        case 'transport_mode_drive':
            return icon_car;
        default:
            return icon_walk;
    }
}
