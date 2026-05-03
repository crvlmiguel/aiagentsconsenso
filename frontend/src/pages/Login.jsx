import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { toast } from "sonner";
import { Logo } from "../components/Brand";
import { Bot, Zap, ShieldCheck, Database } from "lucide-react";

const Login = () => {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, password);
      toast.success("Bem-vindo de volta.");
      nav("/app/painel");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Falha ao iniciar sessão");
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen bg-[#F7F9FC] grid md:grid-cols-2">
      <div className="hidden md:flex flex-col justify-between p-12 bg-gradient-to-br from-[#0069FE] to-[#003F99] text-white relative overflow-hidden">
        <div className="absolute inset-0 opacity-20" style={{
          backgroundImage: "radial-gradient(circle at 20% 20%, #fff 1px, transparent 1px), radial-gradient(circle at 80% 70%, #fff 1px, transparent 1px)",
          backgroundSize: "40px 40px"
        }} />
        <div className="relative">
          <div className="inline-flex items-center gap-2 bg-white/10 backdrop-blur px-3 py-1.5 rounded-full text-xs font-medium">
            <span className="w-1.5 h-1.5 bg-[#7CFFA3] rounded-full live-dot" />
            Consenso+
          </div>
          <h1 className="font-display text-4xl lg:text-5xl font-bold leading-[1.08] mt-8 max-w-md">
            Agentes de IA multilingues que potenciam a comunicação global das empresas.
          </h1>
        </div>
        <div className="relative grid grid-cols-2 gap-4 max-w-md">
          {[
            { icon: Bot, t: "Agentes IA", d: "Multilingues, 24/7" },
            { icon: Database, t: "Dados próprios", d: "Sites, ficheiros, BD" },
            { icon: Zap, t: "Omni-canal", d: "Web, WA, IG, Telegram" },
            { icon: ShieldCheck, t: "Enterprise", d: "Multi-tenant seguro" },
          ].map((f, i) => (
            <div key={i} className="bg-white/10 backdrop-blur rounded-xl p-3 border border-white/10">
              <f.icon size={18} />
              <div className="font-semibold text-sm mt-2">{f.t}</div>
              <div className="text-[11px] text-white/70">{f.d}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="flex items-center justify-center p-6">
        <form data-testid="login-form" onSubmit={onSubmit} className="w-full max-w-sm">
          <div className="md:hidden mb-8"><Logo size={28} /></div>
          <h2 className="font-display text-3xl font-bold text-[#0B1324]">Iniciar sessão</h2>
          <p className="text-[#5B6B82] mt-1.5 text-sm">Aceda à sua plataforma de agentes IA multilingues.</p>

          <div className="mt-8 space-y-4">
            <div>
              <label className="label">Email</label>
              <input data-testid="login-email" type="email" required value={email}
                onChange={(e) => setEmail(e.target.value)} className="input-base"
                placeholder="voce@empresa.pt" />
            </div>
            <div>
              <label className="label">Palavra-passe</label>
              <input data-testid="login-password" type="password" required value={password}
                onChange={(e) => setPassword(e.target.value)} className="input-base" />
            </div>
          </div>

          <button data-testid="login-submit" disabled={loading} className="btn-primary w-full justify-center mt-6 py-3">
            {loading ? "A autenticar…" : "Entrar"}
          </button>

          <div className="flex justify-between text-[13px] text-[#5B6B82] mt-4">
            <Link to="/registar" data-testid="link-register" className="hover:text-[#0069FE] font-medium">
              Criar nova conta
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Login;
