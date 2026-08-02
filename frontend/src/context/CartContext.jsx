import { createContext, useContext, useEffect, useState } from "react";

const CartContext = createContext(null);

export function CartProvider({ children }) {
  const [restaurantId, setRestaurantId] = useState(() => {
    const saved = localStorage.getItem("fd_cart_restaurant");
    return saved ? JSON.parse(saved) : null;
  });
  const [items, setItems] = useState(() => {
    const saved = localStorage.getItem("fd_cart_items");
    return saved ? JSON.parse(saved) : [];
  });

  useEffect(() => {
    localStorage.setItem("fd_cart_items", JSON.stringify(items));
    localStorage.setItem("fd_cart_restaurant", JSON.stringify(restaurantId));
  }, [items, restaurantId]);

  const addItem = (restaurant, menuItem) => {
    if (restaurantId && restaurantId !== restaurant.id) {
      const confirmed = window.confirm(
        `Your cart has items from ${restaurantId ? "another restaurant" : ""}. Start a new cart for ${restaurant.name}?`
      );
      if (!confirmed) return;
      setItems([]);
    }
    setRestaurantId(restaurant.id);
    setItems((prev) => {
      const existing = prev.find((i) => i.menuItem.id === menuItem.id);
      if (existing) {
        return prev.map((i) =>
          i.menuItem.id === menuItem.id ? { ...i, quantity: i.quantity + 1 } : i
        );
      }
      return [...prev, { menuItem, quantity: 1 }];
    });
  };

  const updateQuantity = (menuItemId, quantity) => {
    if (quantity <= 0) {
      setItems((prev) => prev.filter((i) => i.menuItem.id !== menuItemId));
      return;
    }
    setItems((prev) =>
      prev.map((i) => (i.menuItem.id === menuItemId ? { ...i, quantity } : i))
    );
  };

  const clearCart = () => {
    setItems([]);
    setRestaurantId(null);
  };

  const total = items.reduce((sum, i) => sum + i.menuItem.price * i.quantity, 0);
  const itemCount = items.reduce((sum, i) => sum + i.quantity, 0);

  return (
    <CartContext.Provider
      value={{ restaurantId, items, addItem, updateQuantity, clearCart, total, itemCount }}
    >
      {children}
    </CartContext.Provider>
  );
}

export function useCart() {
  return useContext(CartContext);
}
