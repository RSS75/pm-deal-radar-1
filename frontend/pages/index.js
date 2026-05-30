
import { useEffect, useMemo, useState } from "react";

export default function Radar() {
  const [events, setEvents] = useState([]);
  const [search, setSearch] = useState("");
  const [fxOnly, setFxOnly] = useState(false);

  useEffect(() => {
    fetch("https://pm-deal-radar-1-production.up.railway.app/events")
      .then(res => res.json())
      .then(setEvents);
  }, []);

  const filtered = useMemo(() => {
    return events
      .filter(e => e.title.toLowerCase().includes(search.toLowerCase()))
      .filter(e => !fxOnly || e.fx)
      .sort((a, b) => b.priority - a.priority);
  }, [events, search, fxOnly]);

  const grouped = useMemo(() => {
    const groups = {
      "Fund Activity": [],
      "Investments": [],
      "Financing": [],
      "Other": []
    };

    filtered.forEach(e => {
      if (e.event_type === "FUND") groups["Fund Activity"].push(e);
      else if (e.event_type === "INVESTMENT") groups["Investments"].push(e);
      else if (e.event_type === "FINANCING") groups["Financing"].push(e);
      else groups["Other"].push(e);
    });

    return groups;
  }, [filtered]);

  return (
    <div style={{ padding: 30, fontFamily: "Arial", background: "#f5f7fa" }}>
      <h1 style={{ fontSize: 26, fontWeight: "bold" }}>
        Global Private Markets Activity
      </h1>

      {/* FILTER */}
      <div style={{ marginTop: 15 }}>
        <input
          placeholder="Search deals..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{ padding: 8, width: 250 }}
        />
        <label style={{ marginLeft: 10 }}>
          <input type="checkbox" checked={fxOnly} onChange={() => setFxOnly(!fxOnly)} /> FX relevant
        </label>
      </div>

      {/* SECTIONS */}
      {Object.entries(grouped).map(([section, items]) => (
        <div key={section} style={{ marginTop: 30 }}>
          <h2 style={{ fontSize: 20 }}>{section}</h2>

          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
            gap: 15,
            marginTop: 10
          }}>
            {items.map((e, i) => (
              <div key={i} style={{
                background: "white",
                padding: 12,
                borderRadius: 8,
                border: "1px solid #ddd"
              }}>
                <div style={{ fontSize: 12, color: "#666" }}>
                  {e.region} | {e.source}
                </div>

                <div style={{ fontWeight: "bold", marginTop: 5 }}>
                  {e.title}
                </div>

                {/* IMPORTANT NEW SIGNAL LABELS */}
                <div style={{ marginTop: 6, fontSize: 12 }}>
                  {e.event_type === "FUND" && "Fund launch / close"}
                  {e.event_type === "INVESTMENT" && "New investment / acquisition"}
                  {e.event_type === "FINANCING" && "Debt / financing"}
                </div>

                <div style={{ marginTop: 6 }}>
                  {e.fx && <span style={{ background: "#dbeafe", padding: "2px 6px", marginRight: 6 }}>FX</span>}
                  {e.ir && <span style={{ background: "#fee2e2", padding: "2px 6px" }}>IR</span>}
                </div>

                <a href={e.url} target="_blank" style={{ display: "block", marginTop: 8, color: "blue" }}>
                  Open
                </a>
              </div>
            ))}
          </div>
        </div>
      ))}

    </div>
  );
}
