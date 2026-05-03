import React, { createContext, useContext, useEffect, useState } from "react";
import { api } from "./api";

const AuthCtx = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [tenant, setTenant] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    const token = localStorage.getItem("cp_token");
    if (!token) { setLoading(false); return; }
    try {
      const { data } = await api.get("/auth/me");
      setUser(data.user); setTenant(data.tenant);
    } catch { /* ignore */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    localStorage.setItem("cp_token", data.token);
    setUser(data.user); setTenant(data.tenant);
    return data;
  };
  const register = async (payload) => {
    const { data } = await api.post("/auth/register", payload);
    localStorage.setItem("cp_token", data.token);
    setUser(data.user); setTenant(data.tenant);
    return data;
  };
  const logout = () => {
    localStorage.removeItem("cp_token");
    setUser(null); setTenant(null);
    window.location.href = "/iniciar-sessao";
  };

  return (
    <AuthCtx.Provider value={{ user, tenant, loading, login, register, logout, reload: load }}>
      {children}
    </AuthCtx.Provider>
  );
};

export const useAuth = () => useContext(AuthCtx);
