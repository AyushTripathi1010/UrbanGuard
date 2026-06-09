"use client";

import "leaflet/dist/leaflet.css";
import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";

const DEFAULT_CENTER: [number, number] = [18.5204, 73.8567]; // Pune

type Alert = {
  alert_id: string;
  zone_id: string;
  resnet_severity?: number;
  geo?: { lat: number; lon: number } | null;
};

function colorFor(severity: number | undefined) {
  if (severity === undefined) return "#888";
  if (severity >= 0.8) return "#e74c3c";
  if (severity >= 0.55) return "#e67e22";
  return "#f1c40f";
}

export default function HeatmapLayer({ alerts }: { alerts: Alert[] }) {
  return (
    <MapContainer
      center={DEFAULT_CENTER}
      zoom={12}
      style={{ height: "100%", width: "100%" }}
      scrollWheelZoom
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution="&copy; OpenStreetMap contributors"
      />
      {alerts
        .filter(a => a.geo)
        .map(a => (
          <CircleMarker
            key={a.alert_id}
            center={[a.geo!.lat, a.geo!.lon]}
            radius={6 + 6 * (a.resnet_severity ?? 0)}
            pathOptions={{
              color: colorFor(a.resnet_severity),
              fillOpacity: 0.5,
            }}
          >
            <Popup>
              <strong>{a.zone_id}</strong>
              <br />severity: {(a.resnet_severity ?? 0).toFixed(2)}
            </Popup>
          </CircleMarker>
        ))}
    </MapContainer>
  );
}
