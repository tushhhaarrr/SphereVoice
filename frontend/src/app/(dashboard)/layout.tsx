/**
 * Dashboard group layout.
 *
 * Wraps all authenticated dashboard pages with the app shell
 * (sidebar, breadcrumbs, header).
 */

import { AppShell } from "@/components/layout/app-shell";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AppShell>{children}</AppShell>;
}
