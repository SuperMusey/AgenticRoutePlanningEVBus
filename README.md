# AgenticRoutePlanningEVBus
Route planning of EV Buses using Agentic AI
# EV Bus UI Integration README

This README explains exactly what I built, where each file lives, and what the integrator should change later.

---

## 1. Project location

I am keeping the frontend in a separate React project

## 2. How to run the UI locally

From the frontend project folder:

```bash
cd ~/projects/ev-bus-ui
npm install
npm run dev
```

Then open:

```text
http://localhost:5173/
```

---

## 3. Files I created

The important frontend files are:

```text
ev-bus-ui/
├── index.html
├── package.json
├── src/
│   ├── App.jsx
│   ├── main.jsx
│   ├── components/
│   │   └── MapView.jsx
│   ├── data/
│   │   ├── disruptions.json
│   │   └── polylines.js
│   └── styles/
│       └── app.css
```

---

## 4. What each file does

### `index.html`
I load the Google Maps JavaScript API here.

### `src/main.jsx`
I mount the React app here.

### `src/App.jsx`
I render the main page shell here.

### `src/components/MapView.jsx`
I create the Google map here and draw:
- the original route
- the disruption markers
- the disruption blocked-road segments
- the rerouted route

### `src/data/disruptions.json`
I store the custom disruption data here.

### `src/data/polylines.js`
I store the hardcoded original route and hardcoded rerouted route here.

### `src/styles/app.css`
I store the UI styling here.

---

## 5. What the integrator needs to change

There are 4 main things you will eventually replace:

1. Google Maps API key
2. Original route polyline
3. Custom disruptions
4. Rerouted route polyline

---

## 6. Where to add the Google Maps API key

File:

```text
index.html
```

Find this line:

```html
<script src="https://maps.googleapis.com/maps/api/js?key=YOUR_GOOGLE_MAPS_API_KEY" defer></script>
```

Replace:

```text
YOUR_GOOGLE_MAPS_API_KEY
```

with the real Google Maps API key. I have added my API key for now but my billing is off lol

---

## 7. Where to change the original route

File:

```text
src/data/polylines.js
```

I put the original route in:

```js
export const ORIGINAL_ROUTE_PATH = [
  ...
];
```

The integrator should replace this hardcoded path with the real original route path.

Right now this is a coordinate array.

Later, if the backend returns an encoded polyline instead, the integrator can decode it first and then pass the decoded coordinates into the map.

---

## 8. Where to change the rerouted route

File:

```text
src/data/polylines.js
```

I put the rerouted route in:

```js
export const REROUTED_ROUTE_PATH = [
  ...
];
```

The integrator should replace this hardcoded path with the real rerouted route path after the agent or backend produces it.

---

## 9. Where to change the custom disruptions

File:

```text
src/data/disruptions.json
```

I put the current custom disruption records here.

The integrator should replace or expand this file with real custom disruption records from the team database.

### Current disruption format

For a point disruption like an accident:

```json
{
  "id": "d2",
  "title": "Accident near Forbes & Murray",
  "description": "I am marking a single-point disruption here for the UI.",
  "type": "accident",
  "severity": "medium",
  "locationType": "point",
  "point": { "lat": 40.43755, "lng": -79.92395 }
}
```

For a segment disruption like a road closure:

```json
{
  "id": "d1",
  "title": "Road closed on Murray Avenue",
  "description": "I am marking a blocked road segment here for the UI.",
  "type": "road_closure",
  "severity": "high",
  "locationType": "segment",
  "segment": [
    { "lat": 40.43795, "lng": -79.92310 },
    { "lat": 40.43910, "lng": -79.92180 }
  ]
}
```

---

## 10. How the UI currently behaves

Right now, I made the UI do this:

1. Display the original route first
2. Display the custom disruptions from `disruptions.json`
3. Show point disruptions as markers
4. Show blocked roads as red segment lines
5. Show the rerouted route when the user clicks the button

This is currently a prototype with hardcoded data.

---

## 11. What `MapView.jsx` is responsible for

File:

```text
src/components/MapView.jsx
```

This is the main integration file for the map.

### In this file:
- I initialize Google Maps
- I draw the original route
- I draw disruptions
- I draw the rerouted route
- I manage the button that shows or hides the rerouted route

### Important note for the integrator
If the team later fetches data from an API instead of local files, this is the file that should be updated to:
- fetch the original route from backend
- fetch disruptions from backend/database
- fetch rerouted route from backend/agent

---

## 12. Where the route rendering happens

Inside:

```text
src/components/MapView.jsx
```

### Original route drawing
I draw the original route in the function that creates a blue Google Maps polyline.

### Rerouted route drawing
I draw the rerouted route in the function that creates a green Google Maps polyline.

### Disruption segment drawing
I draw blocked road segments in red.

### Disruption marker drawing
I draw point disruptions with markers.

---

## 13. If the backend becomes dynamic later

Right now I am using static files:
- `src/data/disruptions.json`
- `src/data/polylines.js`

Later, the integrator can replace these with API calls.

### Example future backend flow
- `GET /disruptions` -> returns active disruptions
- `GET /route/original` -> returns original polyline
- `POST /route/reroute` -> returns rerouted polyline

Then `MapView.jsx` can call those endpoints and update the map state.

---

## 14. What to keep and what to replace

### Keep
- overall React structure
- Google Maps rendering logic
- legend / sidebar / layout
- disruption visualization logic
- original vs rerouted route layering

### Replace later
- hardcoded original route
- hardcoded rerouted route
- static `disruptions.json`
- hardcoded Google Maps API key in `index.html`

---

## 15. Quick integration checklist

### Required right now
- [ ] Add valid Google Maps API key in `index.html`
- [ ] Confirm map loads locally
- [ ] Confirm original route renders
- [ ] Confirm disruptions render
- [ ] Confirm rerouted route button works

### Replace later
- [ ] Replace `ORIGINAL_ROUTE_PATH`
- [ ] Replace `REROUTED_ROUTE_PATH`
- [ ] Replace `disruptions.json` with real database-backed data
- [ ] Connect reroute generation from backend/agent

---

## 16. Summary for the integrator

If I had to summarize the integration points in one place:

- I put the Google Maps API key in `index.html`
- I put the original route in `src/data/polylines.js`
- I put the rerouted route in `src/data/polylines.js`
- I put the custom disruptions in `src/data/disruptions.json`
- I render everything in `src/components/MapView.jsx`

That is the main handoff.
