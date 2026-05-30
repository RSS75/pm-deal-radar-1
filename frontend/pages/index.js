import { useEffect, useState } from "react";

export default function GPRadar() {
  const [data, setData] = useState([]);
  const [expanded, setExpanded] = useState({});

  useEffect(() => {
    fetch("https://pm-deal-radar-1-production.up.railway.app/events")
      .then(res => res.json())
      .then(setData)
      .catch(console.error);
  }, []);

  const toggle = (i) => {
    setExpanded(prev => ({ ...prev, [i]: !prev[i] }));
  };

  return (
    <div style={page}>
      <h1 style={title}>🌍 GP Activity Intelligence</h1>

      {data.map((gp, i) => {
        const isActive = (gp.activity_count || 0) > 1;

        return (
          <div key={i} style={{ ...gpCard, border: isActive ? "2px solid #2563eb" : "1px solid #e5e7eb" }}>

            {/* HEADER */}
            <div style={gpHeader} onClick={() => toggle(i)}>
              <div>
                <div style={gpName}>{gp.entity}</div>
                <div style={sub}>{gp.activity_count} events</div>
              </div>
              {isActive && <div style={badge}>Active</div>}
            </div>

            {/* EVENTS (COLLAPSIBLE) */}
            {expanded[i] && (
              <div style={eventsGrid}>
                {gp.events.map((e, idx) => (
                  <div key={idx} style={card}>
                    <div style={meta}>{formatType(e.event_type)} | {e.source}</div>
                    <div style={eventTitle}>{e.title}</div>
                    <a href={e.url} target="_blank" rel="noreferrer" style={link}>Open →</a>
                  </div>
                ))}
              </div>
            )}

          </div>
        );
      })}
    </div>
  );
}

function formatType(type) {
  if (type === "FUND_LAUNCH") return "Fund Launch";
  if (type === "FUND_CLOSE") return "Fund Close";
  if (type === "STRUCTURE") return "SPV / Structure";
  if (type === "INVESTMENT") return "Investment";
  return "Other";
}

// STYLES

const page = {
  padding: 24,
  background: "#f3f4f6",
  fontFamily: "Arial",
  minHeight: "100vh"
};

const title = {
  fontSize: 26,
  fontWeight: "bold",
  marginBottom: 20
};

const gpCard = {
  background: "white",
  borderRadius: 8,
  padding: 14,
  marginBottom: 14,
  cursor: "pointer",
  boxShadow: "0 2px 6px rgba(0,0,0,0.06)"
};

const gpHeader = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center"
};

const gpName = {
  fontSize: 18,
  fontWeight: "bold"
};

const sub = {
  fontSize: 12,
  color: "#666"
};

const badge = {
  background: "#dbeafe",
  padding: "4px 8px",
  borderRadius: 6,
  fontSize: 12
};

const eventsGrid = {
  marginTop: 10,
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
  gap: 10
};

const card = {
  background: "#fafafa",
  border: "1px solid #e5e7eb",
  padding: 10,
  borderRadius: 6
};

const meta = {
  fontSize: 11,
  color: "#6b7280"
};

const eventTitle = {
  marginTop: 4,
  fontWeight: "bold",
  fontSize: 14
};

const link = {
  marginTop: 6,
  display: "inline-block",
  fontSize: 12,
  color: "#2563eb"
};
