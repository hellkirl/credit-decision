import type { ReactNode } from "react";
import { useNavigate } from "react-router";

import { clearToken } from "~/lib/auth";
import { useCurrentUser } from "~/routes/protected";

export function LogoutButton() {
  const navigate = useNavigate();
  return (
    <button
      type="button"
      onClick={() => {
        clearToken();
        navigate("/login", { replace: true });
      }}
      className="text-[13px] font-semibold text-[#277AFF]"
    >
      Выйти
    </button>
  );
}

export function AppHeader({ children, className = "sm:px-12" }: { children: ReactNode; className?: string }) {
  const user = useCurrentUser();
  return (
    <header className={`flex min-h-[90px] flex-wrap items-center justify-between gap-4 bg-white px-4 py-3 ${className}`}>
      <div className="flex flex-wrap items-center gap-x-8 gap-y-2">{children}</div>
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
        {user && (
          <div className="text-left text-[13px] leading-[22px] text-[#4A4A4A] sm:text-right sm:leading-[27px]">
            <div className="font-semibold">{user.full_name}</div>
            <div>{user.position}</div>
          </div>
        )}
        <button
          type="button"
          className="h-[37px] rounded-[5px] border border-[#B2B2B2] bg-white px-[15px] text-[13px] font-semibold text-[#4A4A4A] hover:bg-[#F5F6F9]"
        >
          Профиль
        </button>
        <LogoutButton />
      </div>
    </header>
  );
}
