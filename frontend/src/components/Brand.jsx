import React from "react";

export const Logo = ({ size = 28, className = "" }) => (
  <div className={`flex items-center gap-2 ${className}`}>
    <img src="/consenso-icon.png" alt="Consenso+" width={size} height={size}
      style={{ width: size, height: size, objectFit: "contain" }} />
    <div className="flex flex-col leading-none">
      <span className="font-display font-bold text-[17px] text-[#0B1324]">
        Consenso<span className="text-[#0069FE]">+</span>
      </span>
    </div>
  </div>
);
