import { createContext, useContext, useState, useEffect, useCallback } from "react";
import api from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem("user");
    return stored ? JSON.parse(stored) : null;
  });
  const [tenant, setTenant] = useState(() => {
    const stored = localStorage.getItem("tenant");
    return stored ? JSON.parse(stored) : null;
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token) {
      Promise.all([api.get("/auth/me"), api.get("/auth/tenant")])
        .then(([userRes, tenantRes]) => {
          setUser(userRes.data);
          setTenant(tenantRes.data);
          localStorage.setItem("user", JSON.stringify(userRes.data));
          localStorage.setItem("tenant", JSON.stringify(tenantRes.data));
        })
        .catch(() => {
          localStorage.removeItem("token");
          localStorage.removeItem("refresh_token");
          localStorage.removeItem("user");
          localStorage.removeItem("tenant");
          setUser(null);
          setTenant(null);
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  function storeSession(data) {
    localStorage.setItem("token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    localStorage.setItem("user", JSON.stringify(data.user));
    localStorage.setItem("tenant", JSON.stringify(data.tenant));
    setUser(data.user);
    setTenant(data.tenant);
  }

  async function login(email, password) {
    const res = await api.post("/auth/login-json", { email, password });
    storeSession(res.data);
    return res.data.user;
  }

  /** Sign up a brand-new business: creates the Tenant + its first Admin user. */
  async function registerBusiness(businessName, fullName, email, password) {
    const res = await api.post("/auth/register-business", {
      business_name: businessName, full_name: fullName, email, password,
    });
    storeSession(res.data);
    return res.data.user;
  }

  const logout = useCallback(() => {
    const refreshToken = localStorage.getItem("refresh_token");
    if (refreshToken) {
      api.post("/auth/logout", { refresh_token: refreshToken }).catch(() => {});
    }
    localStorage.removeItem("token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("user");
    localStorage.removeItem("tenant");
    setUser(null);
    setTenant(null);
  }, []);

  const isAdmin = user?.role === "admin";

  return (
    <AuthContext.Provider value={{ user, tenant, loading, login, registerBusiness, logout, isAdmin }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
