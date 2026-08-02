import { Link } from "react-router-dom";

export default function RestaurantCard({ restaurant }) {
  return (
    <Link to={`/restaurants/${restaurant.id}`} className="restaurant-card">
      <img src={restaurant.image_url} alt={restaurant.name} />
      <div className="restaurant-card-body">
        <h3>{restaurant.name}</h3>
        <p className="muted">{restaurant.cuisine}</p>
        <div className="restaurant-card-meta">
          <span className="rating">★ {restaurant.rating}</span>
          <span className="muted">{restaurant.address}</span>
        </div>
      </div>
    </Link>
  );
}
