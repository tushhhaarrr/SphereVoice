"use client";

/**
 * App Shell — wraps the entire dashboard layout.
 *
 * Provides:
 * - Collapsible sidebar on desktop / drawer on mobile
 * - Top header with breadcrumbs, theme toggle, user menu
 * - Main content area with proper overflow handling
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, Home, LogOut, Menu, X } from "lucide-react";
import { signOut } from "next-auth/react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Sidebar } from "@/components/layout/sidebar";
import { Breadcrumbs } from "@/components/layout/breadcrumbs";
import { ThemeToggle } from "@/components/theme-toggle";
import { useAuth } from "@/modules/auth";

interface AppShellProps {
    children: React.ReactNode;
}

const SIDEBAR_COLLAPSED_STORAGE_KEY = "SphereVoice.sidebar.collapsed";

export function AppShell({ children }: AppShellProps) {
    const [mounted, setMounted] = useState(false);
    const [mobileOpen, setMobileOpen] = useState(false);
    const [desktopCollapsed, setDesktopCollapsed] = useState(false);
    const { user } = useAuth();
    const pathname = usePathname();
    const isFullscreenAgentEditor = /^\/agents\/[^/]+$/.test(pathname)
        || /^\/workspace\/[^/]+\/agents\/[^/]+$/.test(pathname);

    useEffect(() => {
        // Read localStorage only on the client to avoid SSR/client mismatch
        const stored = window.localStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY);
        if (stored === "true") setDesktopCollapsed(true);
        setMounted(true);
    }, []);

    useEffect(() => {
        if (!mounted) return;
        window.localStorage.setItem(
            SIDEBAR_COLLAPSED_STORAGE_KEY,
            desktopCollapsed ? "true" : "false",
        );
    }, [desktopCollapsed, mounted]);

    const initials = user?.name
        ? user.name
            .split(" ")
            .map((n) => n[0])
            .join("")
            .toUpperCase()
            .slice(0, 2)
        : "V";

    if (isFullscreenAgentEditor) {
        return (
            <div className="flex h-screen flex-col overflow-hidden bg-background">
                <header className="flex h-14 items-center justify-between border-b bg-background px-4 md:px-6">
                    <Button asChild variant="ghost" size="sm" className="gap-2">
                        <Link href="/agents">
                            <Home className="h-4 w-4" />
                            Home
                        </Link>
                    </Button>

                    <div className="flex items-center gap-2">
                        <ThemeToggle />
                        {user && (
                            <div className="flex items-center gap-2">
                                <div className="hidden text-right text-xs sm:block">
                                    <p className="font-medium">{user.name}</p>
                                    <p className="text-muted-foreground">{user.role}</p>
                                </div>
                                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
                                    {initials}
                                </div>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => signOut({ callbackUrl: "/login" })}
                                    aria-label="Sign out"
                                >
                                    <LogOut className="h-4 w-4" />
                                </Button>
                            </div>
                        )}
                    </div>
                </header>

                <main className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto">{children}</main>
            </div>
        );
    }

    return (
        <div className="flex h-screen overflow-hidden bg-background">
            {/* Desktop sidebar */}
            <div className="hidden md:flex">
                <Sidebar collapsed={mounted ? desktopCollapsed : false} />
            </div>

            {/* Mobile overlay */}
            {mobileOpen && (
                <div
                    className="fixed inset-0 z-40 bg-black/50 md:hidden"
                    onClick={() => setMobileOpen(false)}
                    aria-hidden="true"
                />
            )}

            {/* Mobile drawer */}
            <div
                className={cn(
                    "fixed inset-y-0 left-0 z-50 w-64 transform transition-transform duration-200 ease-in-out md:hidden",
                    mobileOpen ? "translate-x-0" : "-translate-x-full",
                )}
            >
                <Sidebar />
                <Button
                    variant="ghost"
                    size="icon"
                    className="absolute right-2 top-3 md:hidden"
                    onClick={() => setMobileOpen(false)}
                    aria-label="Close sidebar"
                >
                    <X className="h-5 w-5" />
                </Button>
            </div>

            {/* Main content */}
            <div className="flex flex-1 flex-col overflow-hidden">
                {/* Header */}
                <header className="flex h-14 items-center gap-4 border-b bg-background px-4 md:px-6">
                    <Button
                        variant="ghost"
                        size="icon"
                        className="md:hidden"
                        onClick={() => setMobileOpen(true)}
                        aria-label="Open sidebar"
                    >
                        <Menu className="h-5 w-5" />
                    </Button>

                    {mounted && (
                        <Button
                            variant="ghost"
                            size="icon"
                            className="hidden md:inline-flex"
                            onClick={() => setDesktopCollapsed((value) => !value)}
                            aria-label={desktopCollapsed ? "Expand sidebar" : "Collapse sidebar"}
                        >
                            {desktopCollapsed ? (
                                <ChevronRight className="h-5 w-5" />
                            ) : (
                                <ChevronLeft className="h-5 w-5" />
                            )}
                        </Button>
                    )}

                    <Breadcrumbs className="hidden md:flex" />

                    <div className="ml-auto flex items-center gap-2">
                        <ThemeToggle />
                        {user && (
                            <div className="flex items-center gap-2">
                                <div className="hidden text-right text-xs sm:block">
                                    <p className="font-medium">{user.name}</p>
                                    <p className="text-muted-foreground">{user.role}</p>
                                </div>
                                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
                                    {initials}
                                </div>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => signOut({ callbackUrl: "/login" })}
                                    aria-label="Sign out"
                                >
                                    <LogOut className="h-4 w-4" />
                                </Button>
                            </div>
                        )}
                    </div>
                </header>

                {/* Page content */}
                <main className="flex-1 overflow-y-auto p-4 md:p-6">{children}</main>
            </div>
        </div>
    );
}
