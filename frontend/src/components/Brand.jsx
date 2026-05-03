import React from "react";

export const Logo = ({ size = 28, className = "" }) => (
  <div className={`flex items-center gap-2 ${className}`}>
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none">
      <rect width="32" height="32" rx="8" fill="#0069FE" />
      <path d="M10 16a6 6 0 1 1 10.39 4.1" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" fill="none" />
      <circle cx="22" cy="22" r="2.4" fill="#fff" />
    </svg>
    <div className="flex flex-col leading-none">
      <span className="font-display font-bold text-[17px] text-[#0B1324]">
        Consenso<span className="text-[#0069FE]">+</span>
      </span>
    </div>
  </div>
);
