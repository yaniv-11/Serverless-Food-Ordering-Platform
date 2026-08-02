import { useEffect, useState } from "react";
import { getRestaurants } from "../api";
import RestaurantCard from "../components/RestaurantCard";

export default function Home() {
  const [restaurants, setRestaurants] = useState([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    getRestaurants()
      .then(setRestaurants)
      .catch(() => setError("Could not load restaurants. Is the backend running?"))
      .finally(() => setLoading(false));
  }, []);

  const filtered = restaurants.filter(
    (r) =>
      r.name.toLowerCase().includes(query.toLowerCase()) ||
      (r.cuisine || "").toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div className="page">
      <div className="hero">
        <h1>Order food you love</h1>
        <input
          className="search-input"
          placeholder="Search restaurants or cuisines..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {loading && <p className="muted center">Loading restaurants...</p>}
      {error && <p className="error center">{error}</p>}

      <div className="restaurant-grid">
        {filtered.map((r) => (
          <RestaurantCard key={r.id} restaurant={r} />
        ))}
      </div>
      {!loading && !error && filtered.length === 0 && (
        <p className="muted center">No restaurants match your search.</p>
      )}
    </div>
  );
}
