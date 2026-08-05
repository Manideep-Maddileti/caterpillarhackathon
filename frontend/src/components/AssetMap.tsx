import { Fragment, useEffect } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, Polyline, useMap } from "react-leaflet";
import L from "leaflet";
import type { Equipment } from "../types";

/** Keeps every equipment marker in view, however spread out the fleet is
 * (this fleet spans multiple Indian cities hundreds of km apart) — a fixed
 * center/zoom on just the first equipment left distant ones off-screen,
 * which looked like "only one coordinate is working". Re-fits whenever the
 * set of live positions changes (new telemetry, new rentals, etc). */
function FitBounds({ positions }: { positions: [number, number][] }) {
  const map = useMap();

  useEffect(() => {
    if (positions.length === 0) return;
    if (positions.length === 1) {
      map.setView(positions[0], 10);
      return;
    }
    const bounds = L.latLngBounds(positions);
    map.fitBounds(bounds, { padding: [30, 30] });
  }, [map, JSON.stringify(positions)]);

  return null;
}

export default function AssetMap({ equipment }: { equipment: Equipment[] }) {
  const withGps = equipment.filter((e) => e.gps_lat != null && e.gps_lng != null);
  const positions: [number, number][] = withGps.map((e) => [e.gps_lat as number, e.gps_lng as number]);
  const fallbackCenter: [number, number] = [22.5, 78.9]; // roughly center of India

  return (
    <div className="h-80">
      <MapContainer center={fallbackCenter} zoom={5} scrollWheelZoom={false}>
        <TileLayer
          attribution='&copy; OpenStreetMap contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitBounds positions={positions} />
        {withGps.map((e) => {
          const nonCompliant = e.tenure?.last_compliant === false;
          const designatedLat = e.tenure?.designated_lat;
          const designatedLng = e.tenure?.designated_lng;
          const showDesignated = nonCompliant && designatedLat != null && designatedLng != null;

          return (
            <Fragment key={e.id}>
              <CircleMarker
                center={[e.gps_lat as number, e.gps_lng as number]}
                radius={7}
                pathOptions={{
                  color: nonCompliant ? "#dc2626" : "#2563eb",
                  fillColor: nonCompliant ? "#dc2626" : "#2563eb",
                  fillOpacity: 0.9,
                  weight: 1,
                }}
              >
                <Popup>
                  <strong>{e.equipment_code}</strong> — {e.type}
                  <br />
                  Status: {e.status}
                  <br />
                  Site: {e.assigned_site?.site_code ?? "Unassigned"}
                  {e.tenure?.tenure_days != null && (
                    <>
                      <br />
                      Tenure: {e.tenure.tenure_days} days
                    </>
                  )}
                  {nonCompliant && (
                    <>
                      <br />
                      <span style={{ color: "#dc2626", fontWeight: 600 }}>Outside designated geofence</span>
                    </>
                  )}
                </Popup>
              </CircleMarker>

              {showDesignated && (
                <>
                  <CircleMarker
                    center={[designatedLat as number, designatedLng as number]}
                    radius={4}
                    pathOptions={{ color: "#64748b", fillColor: "#94a3b8", fillOpacity: 0.8, weight: 1 }}
                  >
                    <Popup>
                      <strong>{e.equipment_code}</strong> designated location
                    </Popup>
                  </CircleMarker>
                  <Polyline
                    positions={[
                      [e.gps_lat as number, e.gps_lng as number],
                      [designatedLat as number, designatedLng as number],
                    ]}
                    pathOptions={{ color: "#dc2626", weight: 1.5, dashArray: "4 4" }}
                  />
                </>
              )}
            </Fragment>
          );
        })}
      </MapContainer>
      <div className="flex items-center gap-4 mt-2 text-xs text-stone-500">
        <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-blue-600 inline-block" /> Live position (in geofence)</span>
        <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-red-600 inline-block" /> Live position (outside geofence)</span>
        <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-stone-400 inline-block" /> Designated location</span>
      </div>
    </div>
  );
}
