import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { toast } from "sonner";
import { Logo } from "../components/Brand";

const Register = () => {
  const { register } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({ company_name: "", name: "", email: "", password: "" });
  const [loading, setLoading] = useState(false);

  const update = (k, v) => setForm({ ...form, [k]: v });

  const onSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await register(form);
      toast.success("Conta criada. Bem-vindo!");
      nav("/app/painel");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Falha ao registar");
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen bg-[#F7F9FC] flex items-center justify-center p-6">
      <form data-testid="register-form" onSubmit={onSubmit}
        className="w-full max-w-md card-surface p-8">
        <div className="flex justify-between items-center mb-6">
          <Logo size={26} />
          <Link to="/iniciar-sessao" data-testid="link-login" className="text-sm text-[#5B6B82] hover:text-[#0069FE]">
            ← Iniciar sessão
          </Link>
        </div>

        <h2 className="font-display text-2xl font-bold">Criar conta</h2>
        <p className="text-sm text-[#5B6B82] mt-1">Comece gratuitamente em segundos.</p>

        <div className="mt-6 space-y-4">
          {[
            { k: "company_name", label: "Nome da empresa", type: "text", tid: "reg-company", placeholder: "Imobiliária Lisboa" },
            { k: "name", label: "O seu nome", type: "text", tid: "reg-name", placeholder: "Maria Silva" },
            { k: "email", label: "Email de trabalho", type: "email", tid: "reg-email", placeholder: "maria@empresa.pt" },
            { k: "password", label: "Palavra-passe", type: "password", tid: "reg-password", placeholder: "Mínimo 6 caracteres" },
          ].map((f) => (
            <div key={f.k}>
              <label className="label">{f.label}</label>
              <input data-testid={f.tid} type={f.type} required
                minLength={f.k === "password" ? 6 : undefined}
                value={form[f.k]} onChange={(e) => update(f.k, e.target.value)}
                placeholder={f.placeholder} className="input-base" />
            </div>
          ))}
        </div>

        <button data-testid="register-submit" disabled={loading}
          className="btn-primary w-full justify-center mt-6 py-3">
          {loading ? "A criar…" : "Criar conta"}
        </button>
      </form>
    </div>
  );
};

export default Register;
