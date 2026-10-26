import { Menu, X } from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router";

import { ApiStatusIndicator } from "@/components/ApiStatus";
import { Button } from "@/components/ui/button";
import { config } from "@/lib/config";
import { cn } from "@/lib/utils";

import { NAV_ITEMS } from "./navigation";

function Brand() {
  return (
    <NavLink to="/" className="flex items-center gap-2 font-semibold tracking-tight">
      <img src="/favicon.svg" alt="" className="size-7" />
      <span className="text-lg">Finlume</span>
    </NavLink>
  );
}

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <ul className="space-y-1">
      {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
        <li key={to}>
          <NavLink
            to={to}
            end={to === "/"}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )
            }
          >
            <Icon aria-hidden="true" className="size-4" />
            {label}
          </NavLink>
        </li>
      ))}
    </ul>
  );
}

function SidebarFooter() {
  return (
    <div className="space-y-1 border-t pt-4">
      <ApiStatusIndicator />
      <p className="text-xs text-muted-foreground">Web client v{config.appVersion} · pre-release</p>
    </div>
  );
}

export function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false);

  // The mobile menu closes on navigation (NavLinks' onNavigate) and on Escape.
  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setMenuOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  return (
    <div className="min-h-dvh md:grid md:grid-cols-[16rem_1fr]">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-card focus:px-3 focus:py-2"
      >
        Skip to content
      </a>

      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-dvh flex-col gap-6 border-r bg-sidebar p-4 md:flex">
        <Brand />
        <nav aria-label="Main" className="flex-1">
          <NavLinks />
        </nav>
        <SidebarFooter />
      </aside>

      {/* Mobile top bar and drawer */}
      <div className="sticky top-0 z-30 flex items-center justify-between border-b bg-background/95 px-4 py-3 backdrop-blur md:hidden">
        <Brand />
        <Button
          variant="ghost"
          size="icon"
          aria-label={menuOpen ? "Close menu" : "Open menu"}
          aria-expanded={menuOpen}
          aria-controls="mobile-nav"
          onClick={() => setMenuOpen((open) => !open)}
        >
          {menuOpen ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}
        </Button>
      </div>
      {menuOpen ? (
        <div className="fixed inset-0 z-20 md:hidden">
          <div className="absolute inset-0 bg-black/40" aria-hidden="true" onClick={() => setMenuOpen(false)} />
          <nav
            id="mobile-nav"
            aria-label="Main"
            className="absolute inset-x-0 top-[3.75rem] space-y-4 border-b bg-sidebar p-4 shadow-lg"
          >
            <NavLinks onNavigate={() => setMenuOpen(false)} />
            <SidebarFooter />
          </nav>
        </div>
      ) : null}

      <main id="main" className="mx-auto w-full max-w-7xl p-4 sm:p-6 lg:p-8">
        <Outlet />
      </main>
    </div>
  );
}
