import { useEffect, useState } from "react";
import { health } from "./api/client";
import "./App.css";

export default function App() {
  const [status, setStatus] = useState("checking…");

  useEffect(() => {
    health()
      .then((d) => setStatus(d.status))
      .catch(() => setStatus("unreachable"));
  }, []);

  return (
    <main style={{ fontFamily: "system-ui", padding: "2rem" }}>
      <h1>HaulRank</h1>
      <p>Transparent load scoring for small carriers.</p>
      <p>
        API health: <strong>{status}</strong>
      </p>
    </main>
  );
}
