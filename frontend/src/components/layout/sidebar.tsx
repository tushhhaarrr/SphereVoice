"use client";

/**
 * Sidebar navigation for the SphereVoice dashboard.
 *
 * Renders the main navigation links with icons, grouped by section.
 * Highlights the active route. Collapses to icons-only on mobile.
 */

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
    Bot,
    Building2,
    ChartBar,
    Globe,
    Headphones,
    History,
    Key,
    Library,
    ListTodo,
    Megaphone,
    Phone,
    Puzzle,
    Radio,
    Settings,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { useAuth } from "@/modules/auth";

interface NavItem {
    label: string;
    href: string;
    icon: React.ComponentType<{ className?: string }>;
    badge?: string;
}

const NAV_ITEMS: NavItem[] = [
    {
        label: "Agents",
        href: "/agents",
        icon: Bot,
    },
    {
        label: "Call History",
        href: "/calls",
        icon: History,
    },
    {
        label: "Live Calls",
        href: "/live",
        icon: Radio,
    },
    {
        label: "Campaigns",
        href: "/campaigns",
        icon: Megaphone,
    },
    {
        label: "Phone Numbers",
        href: "/phone-numbers",
        icon: Phone,
    },
    {
        label: "Knowledge Base",
        href: "/knowledge-base",
        icon: Library,
    },
    {
        label: "Providers",
        href: "/providers",
        icon: Key,
    },
    {
        label: "Analytics",
        href: "/analytics",
        icon: ChartBar,
    },
    {
        label: "Webhooks",
        href: "/webhooks",
        icon: Globe,
    },
    {
        label: "Integrations",
        href: "/integrations",
        icon: Puzzle,
    },
];

const BOTTOM_NAV: NavItem[] = [
    {
        label: "Settings",
        href: "/settings",
        icon: Settings,
    },
];

interface SidebarProps {
    className?: string;
    collapsed?: boolean;
}

export function Sidebar({ className, collapsed = false }: SidebarProps) {
    const pathname = usePathname();
    const { isAdmin } = useAuth();
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
    }, []);

    const tenantsNavItem: NavItem = {
        label: "Tenant Directory",
        href: "/agency/tenants",
        icon: Building2,
    };
    const onboardingNavItem: NavItem = {
        label: "Onboarding Queue",
        href: "/agency/onboarding",
        icon: ListTodo,
    };

    const navItems = isAdmin
        ? [
            ...NAV_ITEMS.slice(0, 8),
            onboardingNavItem,
            tenantsNavItem,
            ...NAV_ITEMS.slice(8),
        ]
        : NAV_ITEMS;

    function isActive(href: string): boolean {
        return pathname.startsWith(href);
    }

    if (!mounted) {
        return (
            <aside
                className={cn(
                    "flex h-full flex-col border-r bg-[var(--sidebar-background)] transition-[width] duration-200",
                    "w-64",
                    className,
                )}
            >
                <div className="flex h-14 items-center border-b px-4">
                    <Link href="/dashboard" className="flex items-center gap-2">
                        <Headphones className="h-6 w-6 text-primary" />
                        <span className="text-lg font-bold tracking-tight">SphereVoice</span>
                    </Link>
                </div>
            </aside>
        );
    }

    return (
        <aside
            className={cn(
                "flex h-full flex-col border-r bg-[var(--sidebar-background)] transition-[width] duration-200",
                collapsed ? "w-[4.5rem]" : "w-64",
                className,
            )}
        >
            {/* Logo / Brand */}
            <div
                className={cn(
                    "flex h-14 items-center border-b",
                    collapsed ? "justify-center px-2" : "px-4",
                )}
            >
                <Link href="/dashboard" className="flex items-center gap-2">
                    <Headphones className="h-6 w-6 text-primary" />
                    {!collapsed ? <span className="text-lg font-bold tracking-tight">SphereVoice</span> : null}
                </Link>
            </div>

            {/* Main navigation */}
            <nav className="flex-1 space-y-1 overflow-y-auto px-2 py-3">
                {navItems.map((item) => {
                    const Icon = item.icon;
                    const active = isActive(item.href);
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            title={collapsed ? item.label : undefined}
                            className={cn(
                                "flex rounded-md py-2 text-sm font-medium transition-colors",
                                collapsed ? "justify-center px-2" : "items-center gap-3 px-3",
                                active
                                    ? "bg-[var(--sidebar-accent)] text-[var(--sidebar-accent-foreground)]"
                                    : "text-[var(--sidebar-foreground)] hover:bg-[var(--sidebar-accent)] hover:text-[var(--sidebar-accent-foreground)]",
                            )}
                        >
                            <Icon className="h-4 w-4 shrink-0" />
                            {!collapsed ? <span>{item.label}</span> : null}
                            {!collapsed && item.badge && (
                                <span className="ml-auto rounded-full bg-primary px-2 py-0.5 text-[10px] font-semibold text-primary-foreground">
                                    {item.badge}
                                </span>
                            )}
                        </Link>
                    );
                })}
            </nav>

            {/* Bottom navigation */}
            <div className="border-t px-2 py-3">
                {BOTTOM_NAV.map((item) => {
                    const Icon = item.icon;
                    const active = isActive(item.href);
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            title={collapsed ? item.label : undefined}
                            className={cn(
                                "flex rounded-md py-2 text-sm font-medium transition-colors",
                                collapsed ? "justify-center px-2" : "items-center gap-3 px-3",
                                active
                                    ? "bg-[var(--sidebar-accent)] text-[var(--sidebar-accent-foreground)]"
                                    : "text-[var(--sidebar-foreground)] hover:bg-[var(--sidebar-accent)] hover:text-[var(--sidebar-accent-foreground)]",
                            )}
                        >
                            <Icon className="h-4 w-4 shrink-0" />
                            {!collapsed ? <span>{item.label}</span> : null}
                        </Link>
                    );
                })}
            </div>
        </aside>
    );
}
