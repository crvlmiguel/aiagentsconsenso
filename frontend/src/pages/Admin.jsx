import React, { useEffect, useState } from "react";
import { api } from "../lib/api";

const Admin = () => {
  const [tenants, setTenants] = useState([]);
  useEffect(() => { api.get("/admin/tenants").then(r => setTenants(r.data)); }, []);

  return (
    <div className="h-full overflow-y-auto p-6 space-y-4" data-testid="admin-page">
      <div>
        <h1 className="text-xl font-bold uppercase tracking-tight">Platform Admin</h1>
        <p className="text-sm text-zinc-500 mt-1">Tenant oversight and global metrics.</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {tenants.map(t => (
          <div key={t.id} className="border border-zinc-800 p-4" data-testid={`admin-tenant-${t.id}`}>
            <div className="flex justify-between items-start">
              <div>
                <div className="label-mono">TENANT</div>
                <div className="text-lg font-bold uppercase">{t.name}</div>
              </div>
              <span className="mono text-[10px] uppercase border border-zinc-700 px-2 py-0.5">{t.plan}</span>
            </div>
            <div className="grid grid-cols-3 gap-2 mt-4 mono text-xs">
              <div>
                <div className="text-zinc-500 text-[10px] uppercase">USERS</div>
                <div className="text-xl font-bold">{t.users || 0}</div>
              </div>
              <div>
                <div className="text-zinc-500 text-[10px] uppercase">CONVOS</div>
                <div className="text-xl font-bold">{t.conversations || 0}</div>
              </div>
              <div>
                <div className="text-zinc-500 text-[10px] uppercase">LEADS</div>
                <div className="text-xl font-bold text-[#FF5500]">{t.leads || 0}</div>
              </div>
            </div>
            <div className="mono text-[10px] text-zinc-500 mt-3">
              {t.slug} · {new Date(t.created_at).toLocaleDateString()}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default Admin;
