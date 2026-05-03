import React from "react";

export const CPLogo = ({ size = 28, className = "" }) => (
  <div className={`flex items-center gap-2 ${className}`}>
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none">
      <rect x="1" y="1" width="30" height="30" stroke="#FAFAFA" strokeWidth="2" />
      <rect x="7" y="7" width="8" height="8" fill="#FF5500" />
      <rect x="17" y="7" width="8" height="8" stroke="#FAFAFA" strokeWidth="2" />
      <rect x="7" y="17" width="18" height="8" fill="#FAFAFA" />
    </svg>
    <span className="mono text-[11px] tracking-[0.25em] uppercase font-bold">
      Consenso<span className="text-[#FF5500]">+</span>
    </span>
  </div>
);

export const Brand = () => (
  <div className="flex flex-col">
    <span className="mono text-[10px] tracking-[0.3em] text-zinc-500 uppercase">
      AI Business OS
    </span>
    <span className="font-bold text-lg tracking-tighter">
      CONSENSO<span className="text-[#FF5500]">+</span>
    </span>
  </div>
);
