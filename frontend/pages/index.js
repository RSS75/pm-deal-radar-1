import { useEffect, useMemo, useState } from "react";

function getSummary(e) {
  const text = e.summary || e.text || e.title || "";
  return text.length > 160 ? text.slice(0, 160) + "..." : text;
}

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
      .filter(e => (e.title || "").toLowerCase().includes(search.toLowerCase()))
      .filter(e => !fxOnly || e.fx)
      .sort((a, b) => b.priority - a.priority);
  }, [events, search, fxOnly]);

  const grouped = useMemo(() => {
    const groups = {
      "New Funds / Launches": [],
      "Fund Closings": [],
      "SPVs / Structures": [],
      "Investments": [],
      "Financing": [],
      "Other": []
    };

    filtered.forEach(e => {
      const text = (e.title || "").toLowerCase();

      if (text.includes("launch") || text.includes("raising") || text.includes("new fund")) {
        groups["New Funds / Launches"].push(e);
      }
      else if (text.includes("close") || text.includes("closed") || text.includes("final close")) {
        groups["Fund Closings"].push(e);
      }
      else if (text.includes("spv") || text.includes("vehicle") || text.includes("structure")) {
        groups["SPVs / Structures"].push(e);
      }
      else if (e.event_type === "INVESTMENT") {
        groups["Investments"].push(e);
      }
      else if (e.event_type === "FINANCING") {
        groups["Financing"].push(e);
      }
      else {
        groups["Other"].push(e);
      }
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
        items.length > 0 && (
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
                  padding: 14,
                  borderRadius: 8,
                  border: "1px solid #ddd",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between"
                }}>

                  <div>
                    <div style={{ fontSize: 12, color: "#666" }}>
                      {e.region} | {e.source}
                    </div>

                    <div style={{ fontWeight: "bold", marginTop: 6 }}>
                      {e.title}
                    </div>

                    {/* ✅ NEW: SUMMARY */}
                    <div style={{ marginTop: 6, fontSize: 13, color: "#444" }}>
                      {getSummary(e)}
                    </div>

                    <div style={{ marginTop: 8 }}>
                      {e.fx && <span style={{ background: "#dbeafe", padding: "2px 6px", marginRight: 6 }}>FX</span>}
                      {e.ir && <span style={{ background: "#fee2e2", padding: "2px 6px" }}>IR</span>}
                    </div>
                  </div>

                  {/* ✅ LINKS */}
                  <div style={{ marginTop: 10 }}>
                    {e.url && (
                      <a href={e.url} target="_blank" rel="noreferrer" style={{ color: "blue", fontSize: 12 }}>
                        Read Article →
                      </a>
                    )}
                  </div>

                </div>
              ))}

            </div>
          </div>
        )
      ))}

    </div>
  );
}
