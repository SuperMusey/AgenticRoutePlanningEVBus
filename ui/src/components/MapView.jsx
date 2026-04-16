import React, { useEffect, useRef, useState } from "react";
import disruptionsData from "../data/disruptions.json";
import {
  ORIGINAL_ROUTE_PATH,
  REROUTED_ROUTE_PATH
} from "../data/polylines";

export default function MapView() {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);

  const originalPolylineRef = useRef(null);
  const reroutedPolylineRef = useRef(null);
  const disruptionSegmentRefs = useRef([]);
  const disruptionMarkerRefs = useRef([]);

  const [showReroute, setShowReroute] = useState(false);

  useEffect(() => {
    if (!window.google || !mapRef.current) return;

    const map = new window.google.maps.Map(mapRef.current, {
      center: { lat: 40.4387, lng: -79.9240 },
      zoom: 15,
      mapTypeControl: false,
      streetViewControl: false,
      fullscreenControl: true
    });

    mapInstanceRef.current = map;

    drawOriginalRoute();
    drawDisruptions();

    return () => {
      clearMapObjects();
    };
  }, []);

  useEffect(() => {
    if (!mapInstanceRef.current) return;

    if (showReroute) {
      drawReroutedRoute();
      fadeOriginalRoute();
    } else {
      removeReroutedRoute();
      restoreOriginalRoute();
    }
  }, [showReroute]);

  const clearMapObjects = () => {
    if (originalPolylineRef.current) {
      originalPolylineRef.current.setMap(null);
    }

    if (reroutedPolylineRef.current) {
      reroutedPolylineRef.current.setMap(null);
    }

    disruptionSegmentRefs.current.forEach((segment) => segment.setMap(null));
    disruptionMarkerRefs.current.forEach((marker) => marker.setMap(null));

    disruptionSegmentRefs.current = [];
    disruptionMarkerRefs.current = [];
  };

  const drawOriginalRoute = () => {
    const map = mapInstanceRef.current;
    if (!map) return;

    // I am drawing the original route here.
    // The integrator should replace ORIGINAL_ROUTE_PATH in polylines.js with the real original polyline path.
    originalPolylineRef.current = new window.google.maps.Polyline({
      path: ORIGINAL_ROUTE_PATH,
      geodesic: true,
      strokeColor: "#2563eb",
      strokeOpacity: 1.0,
      strokeWeight: 5
    });

    originalPolylineRef.current.setMap(map);
  };

  const drawReroutedRoute = () => {
    const map = mapInstanceRef.current;
    if (!map) return;

    if (reroutedPolylineRef.current) {
      reroutedPolylineRef.current.setMap(null);
    }

    // I am drawing the rerouted route here.
    // The integrator should replace REROUTED_ROUTE_PATH in polylines.js with the real rerouted polyline path.
    reroutedPolylineRef.current = new window.google.maps.Polyline({
      path: REROUTED_ROUTE_PATH,
      geodesic: true,
      strokeColor: "#16a34a",
      strokeOpacity: 1.0,
      strokeWeight: 6
    });

    reroutedPolylineRef.current.setMap(map);
  };

  const removeReroutedRoute = () => {
    if (reroutedPolylineRef.current) {
      reroutedPolylineRef.current.setMap(null);
      reroutedPolylineRef.current = null;
    }
  };

  const fadeOriginalRoute = () => {
    if (originalPolylineRef.current) {
      originalPolylineRef.current.setOptions({
        strokeOpacity: 0.35
      });
    }
  };

  const restoreOriginalRoute = () => {
    if (originalPolylineRef.current) {
      originalPolylineRef.current.setOptions({
        strokeOpacity: 1.0
      });
    }
  };

  const getMarkerLabel = (type) => {
    if (type === "road_closure") return "🚧";
    if (type === "accident") return "⚠️";
    if (type === "construction") return "🛠️";
    if (type === "delay") return "⏳";
    return "❗";
  };

  const drawDisruptions = () => {
    const map = mapInstanceRef.current;
    if (!map) return;

    // I am reading the custom disruptions from disruptions.json here.
    // The integrator should replace or expand disruptions.json with real disruption records later.
    disruptionsData.forEach((disruption) => {
      if (disruption.locationType === "point" && disruption.point) {
        const marker = new window.google.maps.Marker({
          position: disruption.point,
          map,
          title: disruption.title,
          label: {
            text: getMarkerLabel(disruption.type),
            fontSize: "18px"
          }
        });

        const infoWindow = new window.google.maps.InfoWindow({
          content: `
            <div style="max-width: 240px;">
              <h3 style="margin: 0 0 8px 0;">${disruption.title}</h3>
              <p style="margin: 0 0 6px 0;"><strong>Type:</strong> ${disruption.type}</p>
              <p style="margin: 0 0 6px 0;"><strong>Severity:</strong> ${disruption.severity}</p>
              <p style="margin: 0;">${disruption.description || ""}</p>
            </div>
          `
        });

        marker.addListener("click", () => {
          infoWindow.open(map, marker);
        });

        disruptionMarkerRefs.current.push(marker);
      }

      if (disruption.locationType === "segment" && disruption.segment) {
        const segmentPolyline = new window.google.maps.Polyline({
          path: disruption.segment,
          geodesic: true,
          strokeColor: "#dc2626",
          strokeOpacity: 1.0,
          strokeWeight: 7
        });

        segmentPolyline.setMap(map);
        disruptionSegmentRefs.current.push(segmentPolyline);

        const middlePoint =
          disruption.segment[Math.floor(disruption.segment.length / 2)];

        const marker = new window.google.maps.Marker({
          position: middlePoint,
          map,
          title: disruption.title,
          label: {
            text: getMarkerLabel(disruption.type),
            fontSize: "18px"
          }
        });

        const infoWindow = new window.google.maps.InfoWindow({
          content: `
            <div style="max-width: 240px;">
              <h3 style="margin: 0 0 8px 0;">${disruption.title}</h3>
              <p style="margin: 0 0 6px 0;"><strong>Type:</strong> ${disruption.type}</p>
              <p style="margin: 0 0 6px 0;"><strong>Severity:</strong> ${disruption.severity}</p>
              <p style="margin: 0;">${disruption.description || ""}</p>
            </div>
          `
        });

        marker.addListener("click", () => {
          infoWindow.open(map, marker);
        });

        disruptionMarkerRefs.current.push(marker);
      }
    });
  };

  return (
    <div className="map-page">
      <aside className="sidebar">
        <h2>Controls</h2>
        <p>
          I am first displaying the original route and the custom disruptions.
        </p>
        <p>
          When I click the button below, I display the rerouted route on top of
          the map.
        </p>

        <button
          className="reroute-button"
          onClick={() => setShowReroute((prev) => !prev)}
        >
          {showReroute ? "Hide rerouted route" : "Show rerouted route"}
        </button>

        <div className="legend">
          <h3>Legend</h3>
          <p><span className="legend-blue"></span> Original route</p>
          <p><span className="legend-red"></span> Disruption / blocked road</p>
          <p><span className="legend-green"></span> Rerouted route</p>
        </div>

        <div className="integration-notes">
          <h3>Integration notes</h3>
          <ul>
            <li>
              I put the original route path in <code>src/data/polylines.js</code>
            </li>
            <li>
              I put the rerouted route path in <code>src/data/polylines.js</code>
            </li>
            <li>
              I put the custom disruptions in <code>src/data/disruptions.json</code>
            </li>
          </ul>
        </div>
      </aside>

      <section className="map-section">
        <div ref={mapRef} className="map-canvas" />
      </section>
    </div>
  );
}