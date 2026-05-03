import React, { useEffect, useState } from "react";
import { api } from "../lib/api";

const Admin = () => {
  const [tenants, setTenants] = useState([]);
  useEffect(() => { api.get("/admin/tenants").then(r => setTenants(r.data)); }, []);

  return (
    <div className="h-full overflow-y-auto p-8 space-y-5" data-testid="admin-page">
      <div>
        <h1 className="font-display text-2xl font-bold">Administração</h1>
        <p className="text-sm text-[#5B6B82] mt-1">Supervisão de tenants e métricas globais.</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {tenants.map(t => (
          <div key={t.id} data-testid={`admin-tenant-${t.id}`} className="card-surface p-5">
            <div className="flex justify-between items-start">
              <div>
                <div className="text-[11px] font-semibold text-[#5B6B82] uppercase tracking-wider">Tenant</div>
                <div className="font-display text-lg font-bold mt-0.5">{t.name}</div>
              </div>
              <span className="badge badge-blue">{t.plan}</span>
            </div>
            <div className="grid grid-cols-3 gap-3 mt-4">
              <div><div className="text-[10px] text-[#5B6B82] uppercase tracking-wider font-semibold">Users</div><div className="font-display text-xl font-bold">{t.users || 0}</div></div>
              <div><div className="text-[10px] text-[#5B6B82] uppercase tracking-wider font-semibold">Conv.</div><div className="font-display text-xl font-bold">{t.conversations || 0}</div></div>
              <div><div className="text-[10px] text-[#5B6B82] uppercase tracking-wider font-semibold">Leads</div><div className="font-display text-xl font-bold text-[#0069FE]">{t.leads || 0}</div></div>
            </div>
            <div className="text-[11px] text-[#5B6B82] mt-3">{t.slug} · {new Date(t.created_at).toLocaleDateString("pt-PT")}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default Admin;
