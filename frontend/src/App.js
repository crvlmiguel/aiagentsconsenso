import React from "react";
import "./App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./lib/auth";
import { Toaster } from "sonner";

import Login from "./pages/Login";
import Register from "./pages/Register";
import AppLayout from "./pages/AppLayout";
import Painel from "./pages/Painel";
import Analytics from "./pages/Analytics";
import Caixa from "./pages/Caixa";
import Construtor from "./pages/Construtor";
import Agentes from "./pages/Agentes";
import Fontes from "./pages/Fontes";
import Leads from "./pages/Leads";
import Tickets from "./pages/Tickets";
import Equipa from "./pages/Equipa";
import Admin from "./pages/Admin";
import Definicoes from "./pages/Definicoes";
import { DemoGeneralista, DemoHotelaria, DemoTurismo } from "./pages/Demos";

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster
          position="top-right"
          richColors
          toastOptions={{
            style: {
              background: "#fff",
              border: "1px solid #E5EAF2",
              borderRadius: 10,
              color: "#0B1324",
              fontSize: 13,
            },
          }}
        />
        <Routes>
          <Route path="/" element={<Navigate to="/iniciar-sessao" replace />} />
          <Route path="/iniciar-sessao" element={<Login />} />
          <Route path="/login" element={<Navigate to="/iniciar-sessao" replace />} />
          <Route path="/registar" element={<Register />} />
          <Route path="/register" element={<Navigate to="/registar" replace />} />
          {/* Public demo landing pages — no auth required */}
          <Route path="/demo" element={<DemoGeneralista />} />
          <Route path="/demo/generalista" element={<DemoGeneralista />} />
          <Route path="/demo/hotelaria" element={<DemoHotelaria />} />
          <Route path="/demo/turismo" element={<DemoTurismo />} />
          <Route path="/app" element={<AppLayout />}>
            <Route index element={<Navigate to="/app/painel" replace />} />
            <Route path="painel" element={<Painel />} />
            <Route path="analytics" element={<Analytics />} />
            <Route path="caixa" element={<Caixa />} />
            <Route path="construtor" element={<Construtor />} />
            <Route path="agentes" element={<Agentes />} />
            <Route path="fontes" element={<Fontes />} />
            <Route path="leads" element={<Leads />} />
            <Route path="tickets" element={<Tickets />} />
            <Route path="canais" element={<Navigate to="/app/agentes" replace />} />
            <Route path="equipa" element={<Equipa />} />
            <Route path="admin" element={<Admin />} />
            <Route path="definicoes" element={<Definicoes />} />
          </Route>
          <Route path="*" element={<Navigate to="/iniciar-sessao" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
