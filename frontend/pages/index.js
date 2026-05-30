import { useEffect, useState } from "react";

export default function GPRadar() {
  const [data, setData] = useState([]);

  useEffect(() => {
    fetch("https://pm-deal-radar-1-production.up.railway.app/events")
      .then(res => res.json())
      .then(setData)
      .catch(console.error);
  }, []);

  return (
    <div style={page}>
      <h1 style={title}>🌍 GP Activity Intelligence</h1>

      {data.map((gp, i) => (
        <div key={i} style={gpCard}>

          {/* HEADER */}
          <div style={gpHeader}>
            <div style={gpName}>{gp.entity}</div>
            <div style={activityCount}>{gp.activity_count} events</div>
          </div>

          {/* TIME CLUSTERS */}
          <div style={activityRow}>
            <Activity label="🔥 6h" value={gp.activity.last_6h} color="#dc2626" />
            <Activity label="🟠 24h" value={gp.activity.last_24h} color="#ea580c" />
            <Activity label="⚪ 48h" value={gp.activity.last_48h} color="#6b7280" />
          </div>

          {/* EVENTS */}
          <div style={eventsSection}>
            {gp.events.map((e, idx) => (
              <div key={idx} style={eventCard}>

                <div style={eventMeta}>
                  {e.event_type} | {e.source}
                </div>

                <div style={eventTitle}>
                  {e.title}
                </div>

                <div style={summary}>
                  {e.summary}
                </div>

                <a
                  href={e.url}
                  target="_blank"
                  rel="noreferrer"
                  style={link}
                >
                  Open →
                </a>

              </div>
            ))}
          </div>

        </div>
      ))}

    </div>
  );
}

// COMPONENTS

function Activity({ label, value, color }) {
  return (
    <div style={{ ...activityBox, borderColor: color }}>
      <div>{label}</div>
      <div style={{ fontWeight: "bold" }}>{value}</div>
    </div>
  );
}

// STYLES

const page = {
  padding: 30,
  background: "#f3f4f6",
  minHeight: "100vh",
  fontFamily: "Arial"
};

const title = {
  fontSize: 28,
  fontWeight: "bold",
  marginBottom: 20
};

const gpCard = {
  background: "white",
  padding: 20,
  borderRadius: 10,
  marginBottom: 20,
  boxShadow: "0 4px 10px rgba(0,0,0,0.08)"
};

const gpHeader = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center"
};

const gpName = {
  fontSize: 20,
  fontWeight: "bold"
};

const activityCount = {
  fontSize: 14,
  color: "#666"
};

const activityRow = {
  display: "flex",
  gap: 10,
  marginTop: 10
};

const activityBox = {
  flex: 1,
  padding: 8,
  border: "2px solid",
  borderRadius: 6,
  textAlign: "center",
  fontSize: 12
};

const eventsSection = {
  marginTop: 15,
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
  gap: 10
};

const eventCard = {
  border: "1px solid #e5e7eb",
  padding: 10,
  borderRadius: 6,
  background: "#fafafa"
};

const eventMeta = {
  fontSize: 11,
  color: "#666"
};

const eventTitle = {
  fontWeight: "bold",
  marginTop: 4,
  fontSize: 14
};

const summary = {
  marginTop: 4,
  fontSize: 12,
  color: "#444"
};

const link = {
  marginTop: 6,
  display: "inline-block",
  fontSize: 12,
  color: "#2563eb"
};
