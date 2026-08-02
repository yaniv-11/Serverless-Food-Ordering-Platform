import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000",
});

// Login/signup are served by a separate Lambda + API Gateway + DynamoDB
// stack, independent of the routes below.
const authApi = axios.create({
  baseURL: import.meta.env.VITE_AUTH_API_URL || import.meta.env.VITE_API_URL || "http://localhost:8000",
});

// Reads the JWT fresh from localStorage on every request, rather than a
// value captured once - so login/logout take effect immediately without
// needing to manually update some shared axios config.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("fd_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const getRestaurants = () => api.get("/restaurants").then((r) => r.data);

export const getRestaurant = (id) =>
  api.get(`/restaurants/${id}`).then((r) => r.data);

export const signup = (name, email, password) =>
  authApi.post("/auth/signup", { name, email, password }).then((r) => r.data);

export const login = (email, password) =>
  authApi.post("/auth/login", { email, password }).then((r) => r.data);

export const placeOrder = (payload) =>
  api.post("/orders", payload).then((r) => r.data);

export const getUserOrders = (userId) =>
  api.get(`/orders/user/${userId}`).then((r) => r.data);

export default api;
