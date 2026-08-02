import { Link } from "react-router-dom";
import { useCart } from "../context/CartContext";
import { useUser } from "../context/UserContext";

export default function Navbar() {
  const { itemCount } = useCart();
  const { user, logout } = useUser();

  return (
    <header className="navbar">
      <Link to="/" className="brand">
        Foodie
      </Link>
      <nav className="nav-links">
        <Link to="/">Restaurants</Link>
        {user && <Link to="/orders">My Orders</Link>}
        <Link to="/cart" className="cart-link">
          Cart
          {itemCount > 0 && <span className="cart-badge">{itemCount}</span>}
        </Link>
        {user ? (
          <button className="link-button" onClick={logout}>
            Logout ({user.name.split(" ")[0]})
          </button>
        ) : (
          <Link to="/login">Login</Link>
        )}
      </nav>
    </header>
  );
}
