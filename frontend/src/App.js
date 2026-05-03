import React from "react";
import "./App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./lib/auth";
import { Toaster } from "sonner";

import Login from "./pages/Login";
import Register from "./pages/Register";
import AppLayout from "./pages/AppLayout";
import Inbox from "./pages/Inbox";
import Agents from "./pages/Agents";
import Leads from "./pages/Leads";
import Tickets from "./pages/Tickets";
import Integrations from "./pages/Integrations";
import Analytics from "./pages/Analytics";
import Team from "./pages/Team";
import Admin from "./pages/Admin";
import Settings from "./pages/Settings";

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster
          theme="dark"
          position="top-right"
          toastOptions={{
            style: {
              background: "#09090B",
              border: "1px solid #27272A",
              borderRadius: 0,
              color: "#FAFAFA",
              fontFamily: "JetBrains Mono, monospace",
              fontSize: 12,
            },
          }}
        />
        <Routes>
          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/app" element={<AppLayout />}>
            <Route index element={<Navigate to="/app/inbox" replace />} />
            <Route path="inbox" element={<Inbox />} />
            <Route path="agents" element={<Agents />} />
            <Route path="leads" element={<Leads />} />
            <Route path="tickets" element={<Tickets />} />
            <Route path="integrations" element={<Integrations />} />
            <Route path="analytics" element={<Analytics />} />
            <Route path="team" element={<Team />} />
            <Route path="admin" element={<Admin />} />
            <Route path="settings" element={<Settings />} />
          </Route>
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
