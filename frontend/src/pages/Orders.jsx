import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { getUserOrders } from "../api";
import { useUser } from "../context/UserContext";

export default function Orders() {
  const { user } = useUser();
  const location = useLocation();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const justPlacedOrderId = location.state?.justPlacedOrderId;

  useEffect(() => {
    if (!user) return;
    getUserOrders(user.id)
      .then(setOrders)
      .finally(() => setLoading(false));
  }, [user]);

  if (!user) {
    return <p className="muted center">Please log in to see your orders.</p>;
  }

  if (loading) return <p className="muted center">Loading orders...</p>;

  return (
    <div className="page">
      <h1>My Orders</h1>
      {orders.length === 0 && <p className="muted center">You haven't placed any orders yet.</p>}
      <div className="order-list">
        {orders.map((order) => (
          <div key={order.id} className="order-card">
            {order.id === justPlacedOrderId && (
              <div className="order-success">Order placed successfully!</div>
            )}
            <div className="order-card-header">
              <h3>{order.restaurant.name}</h3>
              <span className={`status-badge status-${order.status}`}>{order.status}</span>
            </div>
            <p className="muted">
              {new Date(order.created_at).toLocaleString()}
            </p>
            <ul className="order-items">
              {order.items.map((item) => (
                <li key={item.id}>
                  {item.menu_item.name} × {item.quantity} — ₹{item.price * item.quantity}
                </li>
              ))}
            </ul>
            <div className="order-total">Total: ₹{order.total_amount}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
