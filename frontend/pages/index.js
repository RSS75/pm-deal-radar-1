import { useEffect, useMemo, useState } from "react";

export default function GlobalDealRadar() {
  const [events, setEvents] = useState([]);
  const [search, setSearch] = useState("");
  const [fxOnly, setFxOnly] = useState(false);
  const [irOnly, setIrOnly] = useState(false);

  useEffect(() => {
    fetch("https://pm-deal-radar-1-production.up.railway.app/events")
      .then(res => res.json())
      .then(setEvents)
      .catch(console.error);
  }, []);

  const filtered = useMemo(() => {
    return events
      .filter(e => e.title.toLowerCase().includes(search.toLowerCase()))
      .filter(e => !fxOnly || e.fx)
      .filter(e => !irOnly || e.ir)
      .sort((a, b) => b.priority - a.priority);
  }, [events, search, fxOnly, irOnly]);

  const stats = useMemo(() => ({
    total: filtered.length,
    fx: filtered.filter(e => e.fx).length,
    ir: filtered.filter(e => e.ir).length,
    europe: filtered.filter(e => e.region === "EUROPE").length,
    us: filtered.filter(e => e.region === "US").length,
    asia: filtered.filter(e => e.region === "ASIA").length
  }), [filtered]);

  const topDeals = filtered.slice(0, 5);

  return (
    <div style={pageStyle}>

      {/* HEADER */}
      <h1 style={titleStyle}>🌍 Global Private Markets Radar</h1>

      {/* PIPELINE */}
      <div style={panelRow}>
        <StatCard title="Total Deals" value={stats.total} />
        <StatCard title="FX Exposure" value={stats.fx} />
        <StatCard title="IR Exposure" value={stats.ir} />
      </div>

      {/* GLOBAL FLOW VIEW */}
      <div style={panelRow}>
        <StatCard title="Europe" value={stats.europe} />
        <StatCard title="US" value={stats.us} />
        <StatCard title="Asia" value={stats.asia} />
      </div>

      {/* FILTER CONTROLS */}
      <div style={controls}>
        <input
          placeholder="Search deals..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={searchBox}
        />

        <label>
          <input type="checkbox" checked={fxOnly} onChange={() => setFxOnly(!fxOnly)} /> FX only
        </label>

        <label>
          <input type="checkbox" checked={irOnly} onChange={() => setIrOnly(!irOnly)} /> IR only
        </label>
      </div>

      {/* TOP OPPORTUNITIES */}
      <div style={section}>
        <h2>🔥 Top Opportunities</h2>
        <div style={grid}>
          {topDeals.map((e, i) => (
            <EventCard key={i} event={e} highlight />
          ))}
        </div>
      </div>

      {/* FULL LIST */}
      <div style={section}>
        <h2>All Deals</h2>
        <div style={grid}>
          {filtered.map((e, i) => (
            <EventCard key={i} event={e} />
          ))}
        </div>
      </div>

    </div>
  );
}


// ✅ COMPONENTS

function StatCard({ title, value }) {
  return (
    <div style={statCard}>
      <div style={{ fontSize: 12, color: "#666" }}>{title}</div>
      <div style={{ fontSize: 20, fontWeight: "bold" }}>{value}</div>
    </div>
  );
}

function EventCard({ event, highlight }) {
  return (
    <div style={{
      ...card,
      border: highlight ? "2px solid #2563eb" : "1px solid #e5e7eb"
    }}>
      <h3 style={{ fontSize: 15 }}>{event.title}</h3>

      <div style={meta}>
        {event.source} | {event.event_type} | {event.region}
      </div>

      <div style={{ marginTop: 6 }}>
        {event.fx && <span style={badgeFX}>FX</span>}
        {event.ir && <span style={badgeIR}>IR</span>}
      </div>

      <div style={{ marginTop: 6 }}>
        Priority: <b>{event.priority}</b>
      </div>

      <a href={event.url} target="_blank" rel="noopener noreferrer" style={link}>
        Open →
      </a>
    </div>
  );
}


// ✅ STYLES

const pageStyle = {
  padding: 30,
  fontFamily: "Arial",
  background: "#f3f4f6",
  minHeight: "100vh"
};

const titleStyle = {
  fontSize: 28,
  fontWeight: "bold"
};

const panelRow = {
  display: "flex",
  gap: 15,
  marginTop: 15
};

const statCard = {
  background: "white",
  padding: 15,
  borderRadius: 8,
  boxShadow: "0 2px 6px rgba(0,0,0,0.06)"
};

const controls = {
  marginTop: 20,
  display: "flex",
  gap: 10,
  alignItems: "center"
};

const searchBox = {
  padding: 8,
  width: 250
};

const section = {
  marginTop: 25
};

const grid = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
  gap: 15
};

const card = {
  background: "white",
  padding: 12,
  borderRadius: 8,
  boxShadow: "0 3px 6px rgba(0,0,0,0.07)"
};

const meta = {
  fontSize: 12,
  color: "#666",
  marginTop: 5
};

const link = {
  display: "inline-block",
  marginTop: 8,
  color: "#2563eb"
};

const badgeFX = {
  background: "#dbeafe",
  color: "#1d4ed8",
  padding: "2px 6px",
  marginRight: 6,
  borderRadius: 4,
  fontSize: 11
};

const badgeIR = {
  background: "#fee2e2",
  color: "#dc2626",
  padding: "2px 6px",
  borderRadius: 4,
  fontSize: 11
};
