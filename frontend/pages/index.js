import { useEffect, useState } from "react";

export default function Home() {
  const [events, setEvents] = useState([]);
  const [region, setRegion] = useState("All");
  const [fxOnly, setFxOnly] = useState(false);
  const [irOnly, setIrOnly] = useState(false);

  useEffect(() => {
    fetch("https://pm-deal-radar-1-production.up.railway.app/events")
      .then(res => res.json())
      .then(setEvents);
  }, []);

  const filtered = events
    .filter(e => region === "All" || e.region === region)
    .filter(e => !fxOnly || e.fx)
    .filter(e => !irOnly || e.ir)
    .sort((a, b) => b.priority - a.priority);

  const fxTotal = filtered.filter(e => e.fx).length;
  const irTotal = filtered.filter(e => e.ir).length;

  return (
    <div style={{ padding: 20 }}>
      <h1>Private Markets Deal Radar</h1>

      {/* 🔥 GLOBAL PIPELINE PANEL */}
      <div style={{ marginBottom: 20 }}>
        <h2>Hedge Pipeline</h2>
        <p>🌍 Total Deals: {filtered.length}</p>
        <p>💱 FX-sensitive: {fxTotal}</p>
        <p>📉 IR-sensitive: {irTotal}</p>
      </div>

      {/* 🔧 FILTER CONTROLS */}
      <div style={{ marginBottom: 20 }}>
        <select onChange={(e) => setRegion(e.target.value)}>
          <option>All</option>
          <option>Europe</option>
          <option>US</option>
          <option>Asia</option>
          <option>UK</option>
        </select>

        <label style={{ marginLeft: 10 }}>
          <input type="checkbox" onChange={() => setFxOnly(!fxOnly)} />
          FX only
        </label>

        <label style={{ marginLeft: 10 }}>
          <input type="checkbox" onChange={() => setIrOnly(!irOnly)} />
          IR only
        </label>
      </div>

      {/* 📊 DEAL CARDS */}
      {filtered.map((e, i) => (
        <div key={i} style={{ border: "1px solid #ccc", margin: 10, padding: 10 }}>
          <h3>{e.title}</h3>

          <div>
            🌍 {e.region} | {e.asset_class}
          </div>

          <div>
            {e.fx && "💱 FX "}
            {e.ir && "📉 IR "}
            <strong>Priority: {e.priority}</strong>
          </div>

          <div>
            <a href={e.article_url} target="_blank">View Article</a>
          </div>
        </div>
      ))}
    </div>
  );
}
