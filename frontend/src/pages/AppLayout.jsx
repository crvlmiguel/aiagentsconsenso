import React from "react";
import { Outlet, Navigate } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import { useAuth } from "../lib/auth";

const AppLayout = () => {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen bg-[#F7F9FC] flex items-center justify-center">
        <div className="text-sm text-[#5B6B82]">A carregar…</div>
      </div>
    );
  }
  if (!user) return <Navigate to="/iniciar-sessao" replace />;
  return (
    <div className="h-screen grid grid-cols-[256px_1fr] bg-[#F7F9FC]">
      <Sidebar />
      <main className="overflow-hidden" data-testid="app-main"><Outlet /></main>
    </div>
  );
};

export default AppLayout;
