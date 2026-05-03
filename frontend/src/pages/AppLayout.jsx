import React from "react";
import { Outlet, Navigate } from "react-router-dom";
import Sidebar, { MobileTopbar, SidebarProvider } from "../components/Sidebar";
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
    <SidebarProvider>
      <div className="h-screen md:grid md:grid-cols-[256px_1fr] bg-[#F7F9FC] flex flex-col">
        <Sidebar />
        <div className="flex flex-col min-w-0 flex-1 overflow-hidden">
          <MobileTopbar />
          <main className="flex-1 overflow-hidden min-h-0" data-testid="app-main">
            <Outlet />
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
};

export default AppLayout;
