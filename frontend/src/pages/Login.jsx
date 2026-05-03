import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { toast } from "sonner";
import { CPLogo } from "../components/Brand";

const Login = () => {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("demo@consenso.plus");
  const [password, setPassword] = useState("demo1234");
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, password);
      toast.success("Welcome back.");
      nav("/app/inbox");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#09090B] text-white grid grid-cols-1 md:grid-cols-[1fr_480px]">
      {/* Left pane: big control-room look */}
      <div className="hidden md:flex flex-col justify-between p-10 border-r border-zinc-800 grid-bg relative">
        <CPLogo size={32} />
        <div className="space-y-3 max-w-md">
          <div className="label-mono">SYS_VERSION / 1.0.0</div>
          <h1 className="text-4xl font-extrabold tracking-tighter uppercase leading-none">
            The AI operating system for
            <span className="text-[#FF5500]"> modern businesses.</span>
          </h1>
          <p className="text-sm text-zinc-400 leading-relaxed">
            Unify every inbox. Structure every conversation. Automate every
            workflow. One platform. Every channel.
          </p>
        </div>
        <div className="grid grid-cols-3 gap-4 mono text-[10px] text-zinc-500 uppercase tracking-widest">
          <div className="border border-zinc-800 p-3">
            <div className="text-white text-xl font-bold">05</div>
            channels unified
          </div>
          <div className="border border-zinc-800 p-3">
            <div className="text-white text-xl font-bold">03</div>
            LLM providers
          </div>
          <div className="border border-zinc-800 p-3">
            <div className="text-[#FF5500] text-xl font-bold">∞</div>
            automations
          </div>
        </div>
      </div>

      {/* Right pane: form */}
      <div className="flex items-center justify-center p-6">
        <form
          data-testid="login-form"
          onSubmit={onSubmit}
          className="w-full max-w-sm space-y-6"
        >
          <div>
            <div className="label-mono mb-1">ACCESS / LOG IN</div>
            <h2 className="text-2xl font-bold tracking-tight uppercase">
              Enter the system
            </h2>
          </div>

          <div className="space-y-3">
            <div>
              <label className="label-mono block mb-1">EMAIL</label>
              <input
                data-testid="login-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-[#18181B] border border-zinc-800 focus:border-white outline-none px-3 py-2.5 text-sm mono"
                placeholder="you@company.com"
              />
            </div>
            <div>
              <label className="label-mono block mb-1">PASSWORD</label>
              <input
                data-testid="login-password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-[#18181B] border border-zinc-800 focus:border-white outline-none px-3 py-2.5 text-sm mono"
              />
            </div>
          </div>

          <button
            data-testid="login-submit"
            disabled={loading}
            className="w-full bg-white text-black py-3 font-bold mono text-xs uppercase tracking-widest hover:bg-zinc-200 disabled:opacity-50"
          >
            {loading ? "Authenticating…" : "Log in →"}
          </button>

          <div className="text-xs text-zinc-500 flex justify-between mono uppercase tracking-widest">
            <Link
              to="/register"
              data-testid="link-register"
              className="hover:text-white"
            >
              New tenant? Register
            </Link>
            <span>Demo: demo / demo1234</span>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Login;
