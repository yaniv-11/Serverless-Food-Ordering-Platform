import { createContext, useContext, useEffect, useState } from "react";

const UserContext = createContext(null);

export function UserProvider({ children }) {
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem("fd_user");
    return saved ? JSON.parse(saved) : null;
  });
  const [token, setToken] = useState(() => localStorage.getItem("fd_token"));

  useEffect(() => {
    if (user) {
      localStorage.setItem("fd_user", JSON.stringify(user));
    } else {
      localStorage.removeItem("fd_user");
    }
  }, [user]);

  useEffect(() => {
    if (token) {
      localStorage.setItem("fd_token", token);
    } else {
      localStorage.removeItem("fd_token");
    }
  }, [token]);

  const setSession = (userData, authToken) => {
    setUser(userData);
    setToken(authToken);
  };

  const logout = () => {
    setUser(null);
    setToken(null);
  };

  return (
    <UserContext.Provider value={{ user, token, setSession, logout }}>
      {children}
    </UserContext.Provider>
  );
}

export function useUser() {
  return useContext(UserContext);
}
