"use client";

/**
 * Global Integrations page — read-only overview that directs users
 * to enter a tenant workspace to manage CRM integrations.
 *
 * CRM connect/disconnect/settings are only available inside
 * /workspace/[tenantId]/integrations because tokens are per-tenant.
 */

import { Puzzle } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function IntegrationsGlobalPage() {
  return (
    <div className="p-6 lg:p-8 space-y-8">
      <div className="flex items-center gap-3">
        <Puzzle className="h-6 w-6 text-primary" />
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Integrations</h1>
          <p className="text-sm text-muted-foreground">
            Connect your CRM and other tools to automate workflows with voice agents.
          </p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Tenant-scoped integrations</CardTitle>
          <CardDescription>
            CRM integrations are configured per tenant. Open a tenant workspace from
            the <strong>Tenant Directory</strong> and navigate to the{" "}
            <strong>Integrations</strong> tab to connect Zoho CRM.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {["Zoho CRM", "HubSpot", "Salesforce", "Freshdesk"].map((name) => (
              <div
                key={name}
                className="flex items-center gap-3 rounded-xl border bg-muted/20 px-4 py-5 opacity-50"
              >
                <div className="h-9 w-9 rounded-md bg-muted flex items-center justify-center text-xs font-bold text-muted-foreground">
                  {name[0]}
                </div>
                <div>
                  <p className="font-medium text-sm">{name}</p>
                  <p className="text-xs text-muted-foreground">
                    {name === "Zoho CRM" ? "Available — connect in tenant workspace" : "Coming soon"}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
