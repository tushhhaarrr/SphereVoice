import { redirect } from "next/navigation";

/**
 * Root page — redirects to the dashboard.
 * The dashboard lives under the (dashboard) route group.
 */
export default function RootPage() {
  redirect("/dashboard");
}
