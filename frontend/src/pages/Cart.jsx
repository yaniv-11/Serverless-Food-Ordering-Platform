import { loadStripe } from "@stripe/stripe-js";
import { CardElement, Elements, useElements, useStripe } from "@stripe/react-stripe-js";
import { useNavigate } from "react-router-dom";
import { useState } from "react";
import { useCart } from "../context/CartContext";
import { useUser } from "../context/UserContext";
import { placeOrder } from "../api";

const stripePromise = loadStripe(import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY);

function CheckoutForm() {
  const { items, restaurantId, clearCart, total } = useCart();
  const { user } = useUser();
  const navigate = useNavigate();
  const stripe = useStripe();
  const elements = useElements();
  const [placing, setPlacing] = useState(false);
  const [error, setError] = useState(null);

  const handleCheckout = async () => {
    if (!user) {
      navigate("/login");
      return;
    }
    if (!stripe || !elements) return;

    setPlacing(true);
    setError(null);
    try {
      // user_id is no longer sent here - the backend reads it from the
      // verified JWT (via the API Gateway authorizer), never from the body.
      const order = await placeOrder({
        restaurant_id: restaurantId,
        items: items.map((i) => ({ menu_item_id: i.menuItem.id, quantity: i.quantity })),
      });

      const result = await stripe.confirmCardPayment(order.client_secret, {
        payment_method: { card: elements.getElement(CardElement) },
      });

      if (result.error) {
        setError(result.error.message);
        return;
      }

      clearCart();
      navigate("/orders", { state: { justPlacedOrderId: order.id } });
    } catch (e) {
      setError(e.response?.data?.detail || "Could not place order. Please try again.");
    } finally {
      setPlacing(false);
    }
  };

  return (
    <>
      <div className="card-input">
        <CardElement options={{ style: { base: { fontSize: "16px" } } }} />
      </div>
      {error && <p className="error center">{error}</p>}
      <button
        className="btn btn-primary btn-block"
        onClick={handleCheckout}
        disabled={placing || (!!user && !stripe)}
      >
        {placing ? "Processing payment..." : user ? `Pay ₹${total}` : "Login to Checkout"}
      </button>
    </>
  );
}

export default function Cart() {
  const { items, updateQuantity, total } = useCart();

  if (items.length === 0) {
    return (
      <div className="page">
        <h1>Your Cart</h1>
        <p className="muted center">Your cart is empty. Go add something tasty!</p>
      </div>
    );
  }

  return (
    <div className="page">
      <h1>Your Cart</h1>
      <div className="cart-list">
        {items.map(({ menuItem, quantity }) => (
          <div key={menuItem.id} className="cart-row">
            <div>
              <h4>{menuItem.name}</h4>
              <span className="muted">₹{menuItem.price} each</span>
            </div>
            <div className="qty-control">
              <button onClick={() => updateQuantity(menuItem.id, quantity - 1)}>−</button>
              <span>{quantity}</span>
              <button onClick={() => updateQuantity(menuItem.id, quantity + 1)}>+</button>
            </div>
            <span className="price">₹{menuItem.price * quantity}</span>
          </div>
        ))}
      </div>

      <div className="cart-summary">
        <span>Total</span>
        <span className="price">₹{total}</span>
      </div>

      <Elements stripe={stripePromise}>
        <CheckoutForm />
      </Elements>
    </div>
  );
}
