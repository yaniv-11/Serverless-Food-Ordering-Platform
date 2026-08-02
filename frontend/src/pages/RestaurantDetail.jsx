import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getRestaurant } from "../api";
import MenuItemCard from "../components/MenuItemCard";
import { useCart } from "../context/CartContext";

export default function RestaurantDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { addItem } = useCart();
  const [restaurant, setRestaurant] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getRestaurant(id)
      .then(setRestaurant)
      .catch(() => setError("Restaurant not found."));
  }, [id]);

  if (error) return <p className="error center">{error}</p>;
  if (!restaurant) return <p className="muted center">Loading menu...</p>;

  const categories = [...new Set(restaurant.menu_items.map((m) => m.category))];

  return (
    <div className="page">
      <button className="link-button back-link" onClick={() => navigate(-1)}>
        ← Back
      </button>
      <div className="restaurant-header">
        <img src={restaurant.image_url} alt={restaurant.name} />
        <div>
          <h1>{restaurant.name}</h1>
          <p className="muted">{restaurant.cuisine}</p>
          <p className="muted">{restaurant.address}</p>
          <span className="rating">★ {restaurant.rating}</span>
        </div>
      </div>

      {categories.map((category) => (
        <div key={category} className="menu-category">
          <h2>{category}</h2>
          <div className="menu-grid">
            {restaurant.menu_items
              .filter((m) => m.category === category)
              .map((item) => (
                <MenuItemCard
                  key={item.id}
                  item={item}
                  onAdd={() => addItem(restaurant, item)}
                />
              ))}
          </div>
        </div>
      ))}
    </div>
  );
}
