import React from "react";
import { Outlet, Navigate } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import { useAuth } from "../lib/auth";

const AppLayout = () => {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen bg-[#09090B] text-white flex items-center justify-center">
        <div className="mono text-xs text-zinc-500 uppercase tracking-widest">Loading…</div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;

  return (
    <div className="h-screen grid grid-cols-[256px_1fr] bg-[#09090B] text-white">
      <Sidebar />
      <main className="overflow-hidden" data-testid="app-main">
        <Outlet />
      </main>
    </div>
  );
};

export default AppLayout;
