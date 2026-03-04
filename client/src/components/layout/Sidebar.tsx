import { Link, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  Bot,
  Settings,
  Store,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/useAuth";

const NAV_ITEMS = [
  { label: "Dashboard", icon: LayoutDashboard, href: "/dashboard" },
  { label: "AI Assistant", icon: Bot, href: "/dashboard/assistant" },
  { label: "Marketplaces", icon: Store, href: "/dashboard/marketplaces" },
  { label: "Settings", icon: Settings, href: "/dashboard/settings" },
];

export function Sidebar() {
  const location = useLocation();
  const { user } = useAuth();

  return (
    <aside className="flex h-screen w-64 flex-col border-r bg-sidebar text-sidebar-foreground">
      {/* Logo */}
      <div className="flex h-16 items-center gap-2 border-b border-sidebar-border px-4">
        <img src="/abc.png" alt="RetailSutra" className="h-9 w-9 rounded-lg object-contain" />
        <div className="flex flex-col">
          <span className="text-sm font-bold text-white">RetailSutra</span>
          <span className="text-xs text-sidebar-foreground/60">
            {user?.full_name || "Seller"}
          </span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-3 py-4">
        {NAV_ITEMS.map((item) => {
          const isActive =
            item.href === "/dashboard"
              ? location.pathname === "/dashboard"
              : location.pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              to={item.href}
              className={cn(
                "mb-1 flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                isActive
                  ? "bg-sidebar-accent text-orange-400 font-medium"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground"
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* User */}
      <div className="border-t border-sidebar-border p-4">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-sidebar-accent text-xs font-medium text-sidebar-foreground">
            {user?.full_name?.charAt(0) || "U"}
          </div>
          <div className="flex flex-col text-xs">
            <span className="font-medium text-sidebar-foreground">{user?.full_name}</span>
            <span className="text-sidebar-foreground/60">{user?.email}</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
