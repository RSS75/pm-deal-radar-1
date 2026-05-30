import { useEffect, useState } from "react";

export default function Home() {
  const [events, setEvents] = useState([]);

  useEffect(() => {
    fetch(process.env.NEXT_PUBLIC_API)
      .then(res => res.json())
      .then(data => setEvents(data));
  }, []);

  return (
    <div style={{ padding: 20 }}>
      <h1>Private Markets Deal Radar</h1>

      {events.map((e, i) => (
        <div key={i} style={{ border: "1px solid #ccc", margin: 10, padding: 10 }}>
          <h3>{e.title}</h3>

          <div>
            {e.fx ? "FX " : ""}
            {e.ir ? "IR " : ""}
            {e.region}
          </div>

          <div>
            <a href={e.article_url} target="_blank">News</a> |{" "}
            <a href={e.manager_url} target="_blank">Manager</a>
          </div>
        </div>
      ))}
    </div>
  );
}
