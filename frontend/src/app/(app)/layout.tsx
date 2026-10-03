"use client";

import clsx from "clsx";
import {
  BarChart3,
  Boxes,
  LayoutDashboard,
  LogOut,
  Package,
  Receipt,
  Settings,
  ShoppingCart,
  Shirt,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { Spinner } from "@/components/ui";
import { useAuth } from "@/lib/auth";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard, adminOnly: true },
  { href: "/pos", label: "Point of Sale", icon: ShoppingCart },
  { href: "/sales", label: "Sales & Invoices", icon: Receipt },
  { href: "/products", label: "Products", icon: Package },
  { href: "/inventory", label: "Inventory", icon: Boxes },
  { href: "/reports", label: "Reports", icon: BarChart3, adminOnly: true },
  { href: "/settings", label: "Settings", icon: Settings, adminOnly: true },
];

/** Paths a cashier can open. Admin-only pages are also enforced by the API. */
function allowed(path: string, isAdmin: boolean) {
  if (isAdmin) return true;
  return NAV.some((n) => !n.adminOnly && n.href !== "/" && path.startsWith(n.href));
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const isAdmin = user?.role === "admin";

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace("/login");
    else if (!allowed(pathname, isAdmin)) router.replace("/pos");
  }, [loading, user, pathname, isAdmin, router]);

  if (loading || !user || !allowed(pathname, isAdmin)) return <Spinner />;

  return (
    <div className="flex min-h-screen">
      <aside className="no-print sticky top-0 flex h-screen w-56 shrink-0 flex-col border-r border-slate-200 bg-white">
        <div className="flex items-center gap-2 px-5 py-5 text-brand-600">
          <Shirt size={22} />
          <span className="font-semibold text-slate-900">Store IMS</span>
        </div>
        <nav className="flex-1 space-y-1 px-3">
          {NAV.filter((n) => isAdmin || !n.adminOnly).map(({ href, label, icon: Icon }) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={clsx(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium",
                  active ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100",
                )}
              >
                <Icon size={18} />
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-slate-200 p-4">
          <p className="truncate text-sm font-medium">{user.name}</p>
          <p className="text-xs capitalize text-slate-500">{user.role}</p>
          <button
            onClick={logout}
            className="mt-3 flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900"
          >
            <LogOut size={16} /> Sign out
          </button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 p-6 lg:p-8">{children}</main>
    </div>
  );
}
