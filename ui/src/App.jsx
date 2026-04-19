import React from "react";
import MapView from "./components/MapView";

export default function App() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <h1>EV Bus Disruption & Rerouting Map</h1>
        <p>
          I am first displaying the original route, then the custom disruptions,
          and then the rerouted route.
        </p>
      </header>

      <main className="content">
        <MapView />
      </main>
    </div>
  );
}