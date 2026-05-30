import { useEffect, useState, useRef } from "react";

const API = process.env.NEXT_PUBLIC_API || "https://your-api  const intervalRef = useRef(null);const API = process.env.NEXT_PUBLIC_API || "https://your-api-url/events";
  const isMounted = useRef(true);

  // ============================================================
  // FETCH FUNCTION (CONTROLLED)
  // ============================================================

  const fetchData = async () => {
    try {
      const res = await fetch(API);

      if (!res.ok) return;

      const json = await res.json();

      if (!isMounted.current) return;

      // ✅ Hard limit to protect browser memory
      const trimmed = json.slice(0, 20);

      setData(trimmed);
      setLoading(false);
      setLastUpdated(new Date().toLocaleTimeString());

    } catch (err) {
      console.error("Fetch failed:", err);
    }
  };

  // ============================================================
  // EFFECT (CONTROLLED POLLING)
  // ============================================================

  useEffect(() => {
    isMounted.current = true;

    fetchData();

    // ✅ Poll every 30 seconds (matches backend)
    intervalRef.current = setInterval(fetchData, 30000);

    return () => {
      isMounted.current = false;
      clearInterval(intervalRef.current);
    };
  }, []);

  // ============================================================
  // SORT BY ACTIVITY
  // ============================================================

  const sorted = [...data].sort(
    (a, b) => b.activity_count - a.activity_count
  );

  // ============================================================
  // UI
  // ============================================================

  if (loading) {
    return (
      <div style={styles.container}>
        <h2>Loading GP Activity…</h2>
      </div>
    );
  }

  return (
    <div style={styles.container}>

      <div style={styles.header}>
        <h1>GP Activity Monitor</h1>
        <div style={styles.meta}>
          Last updated: {lastUpdated}
        </div>
      </div>

      <div style={styles.list}>
        {sorted.map((gp, i) => (
          <GPCard key={i} gp={gp} />
        ))}
      </div>
    </div>
  );
}

//////////////////////////////////////////////////////////////
// GP CARD COMPONENT (MEMORY SAFE)
//////////////////////////////////////////////////////////////

function GPCard({ gp }) {
  const [open, setOpen] = useState(false);

  const toggle = () => setOpen(!open);

  return (
    <div style={styles.card}>

      {/* HEADER */}
      <div style={styles.cardHeader} onClick={toggle}>
        <div>
          <div style={styles.entity}>{gp.entity}</div>
          <div style={styles.count}>
            {gp.activity_count} signals
          </div>
        </div>

        <div style={styles.badge(gp.activity_count)}>
          {activityLabel(gp.activity_count)}
        </div>
      </div>

      {/* EVENTS */}
      {open && (
        <div style={styles.events}>
          {gp.events.map((e, j) => (
            <EventItem key={j} event={e} />
          ))}
        </div>
      )}

    </div>
  );
}

//////////////////////////////////////////////////////////////
// EVENT COMPONENT (LIGHTWEIGHT)
//////////////////////////////////////////////////////////////

function EventItem({ event }) {
  return (
    <div style={styles.event}>
      <div style={styles.eventMeta}>
        {event.source} | {formatType(event.event_type)}
      </div>

      <div style={styles.eventTitle}>
        <a href={event.url} target="_blank" rel="noreferrer">
          {event.title}
        </a>
      </div>
    </div>
  );
}

//////////////////////////////////////////////////////////////
// HELPERS
//////////////////////////////////////////////////////////////

function formatType(type) {
  if (type === "FUND") return "Fund";
  if (type === "INVESTMENT") return "Investment";
  if (type === "STRUCTURE") return "Structure";
  return "Other";
}

function activityLabel(count) {
  if (count >= 5) return "High";
  if (count >= 3) return "Active";
  return "Low";
}

//////////////////////////////////////////////////////////////
// STYLES (LIGHTWEIGHT — NO LIBS)
//////////////////////////////////////////////////////////////

const styles = {
  container: {
    padding: 20,
    background: "#f5f7fa",
    minHeight: "100vh",
    fontFamily: "Arial"
  },

  header: {
    marginBottom: 20
  },

  meta: {
    fontSize: 12,
    color: "#666"
  },

  list: {
    display: "flex",
    flexDirection: "column",
    gap: "12px"
  },

  card: {
    background: "#fff",
    padding: 12,
    borderRadius: 8,
    boxShadow: "0 2px 4px rgba(0,0,0,0.07)"
  },

  cardHeader: {
    display: "flex",
    justifyContent: "space-between",
    cursor: "pointer"
  },

  entity: {
    fontWeight: "bold",
    fontSize: 16
  },

  count: {
    fontSize: 12,
    color: "#888"
  },

  badge: (count) => ({
    padding: "4px 8px",
    borderRadius: 6,
    fontSize: 12,
    background:
      count >= 5 ? "#fecaca" :
      count >= 3 ? "#fde68a" :
      "#e5e7eb"
  }),

  events: {
    marginTop: 10,
    display: "flex",
    flexDirection: "column",
    gap: "8px"
  },

  event: {
    padding: 8,
    border: "1px solid #eee",
    borderRadius: 6
  },

  eventMeta: {
    fontSize: 10,
    color: "#777"
  },

  eventTitle: {
    fontSize: 13,
    fontWeight: "bold"
  }
};

export default function Home() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);

