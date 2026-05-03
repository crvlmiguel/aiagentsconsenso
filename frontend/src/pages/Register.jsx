import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { toast } from "sonner";
import { CPLogo } from "../components/Brand";

const Register = () => {
  const { register } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({
    company_name: "",
    name: "",
    email: "",
    password: "",
  });
  const [loading, setLoading] = useState(false);

  const update = (k, v) => setForm({ ...form, [k]: v });

  const onSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await register(form);
      toast.success("Tenant created. Welcome!");
      nav("/app/inbox");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#09090B] text-white flex items-center justify-center p-6">
      <form
        data-testid="register-form"
        onSubmit={onSubmit}
        className="w-full max-w-md border border-zinc-800 bg-[#09090B] p-8 space-y-5"
      >
        <div className="flex justify-between items-center">
          <CPLogo size={24} />
          <Link to="/login" data-testid="link-login" className="label-mono hover:text-white">
            ← Log in
          </Link>
        </div>

        <div>
          <div className="label-mono mb-1">NEW_TENANT / INIT</div>
          <h2 className="text-2xl font-bold uppercase tracking-tight">Create your workspace</h2>
        </div>

        <div className="space-y-3">
          {[
            { k: "company_name", label: "Company name", type: "text", tid: "reg-company" },
            { k: "name", label: "Your name", type: "text", tid: "reg-name" },
            { k: "email", label: "Work email", type: "email", tid: "reg-email" },
            { k: "password", label: "Password", type: "password", tid: "reg-password" },
          ].map((f) => (
            <div key={f.k}>
              <label className="label-mono block mb-1">{f.label.toUpperCase()}</label>
              <input
                data-testid={f.tid}
                type={f.type}
                required
                minLength={f.k === "password" ? 6 : undefined}
                value={form[f.k]}
                onChange={(e) => update(f.k, e.target.value)}
                className="w-full bg-[#18181B] border border-zinc-800 focus:border-white outline-none px-3 py-2.5 text-sm mono"
              />
            </div>
          ))}
        </div>

        <button
          data-testid="register-submit"
          disabled={loading}
          className="w-full bg-white text-black py-3 font-bold mono text-xs uppercase tracking-widest hover:bg-zinc-200 disabled:opacity-50"
        >
          {loading ? "Creating…" : "Create tenant →"}
        </button>
      </form>
    </div>
  );
};

export default Register;
