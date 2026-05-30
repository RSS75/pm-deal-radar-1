import { useEffect, useState } from "react";

export default function Home() {
  const [events, setEvents] = useState([]);

  useEffect(() => {
    fetch("https://pm-deal-radar-1-production.up.railway.app/events")
      .then(res => res.json())
      .then(data => {
        console.log("DATA:", data);
        setEvents(data);
      })
      .catch(err => console.error("ERROR:", err));
  }, []);

  return (
    <div style={{ padding: 20 }}>
      <h1>Private Markets Deal Radar</h1>

      {events.length === 0 && <p>Loading data...</p>}

      {events.map((e, i) => (
        <div key={i} style={{ border: "1px solid #ccc", margin: 10, padding: 10 }}>
          
          <h3>{e.title}</h3>

          <a href={e.article_url} target="_blank" rel="noopener noreferrer">
            View Article
          </a>

        </div>
      ))}
    </div>
  );
}
