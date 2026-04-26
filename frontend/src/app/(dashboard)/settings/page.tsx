"use client";

import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AuditLogTable, UsersTable, useAuditLogs, useTenants, useUsers } from "@/modules/analytics";
import { useAuth } from "@/modules/auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function SettingsPage() {
  const { isAdmin, isLoading } = useAuth();

  // Users state
  const [userSearch, setUserSearch] = useState("");
  const [userPage, setUserPage] = useState(1);
  const [userTenantId, setUserTenantId] = useState("");
  const users = useUsers({
    enabled: isAdmin && !isLoading,
    tenantId: userTenantId || undefined,
    search: userSearch || undefined,
    page: userPage,
    limit: 50,
  });

  // Audit log state
  const [auditPage, setAuditPage] = useState(1);
  const [resourceTypeFilter, setResourceTypeFilter] = useState("all");
  const [actionFilter, setActionFilter] = useState("all");
  const [auditTenantId, setAuditTenantId] = useState("");
  const auditLogs = useAuditLogs({
    enabled: isAdmin && !isLoading,
    tenantId: auditTenantId || undefined,
    resourceType: resourceTypeFilter !== "all" ? resourceTypeFilter : undefined,
    action: actionFilter !== "all" ? actionFilter : undefined,
    page: auditPage,
    limit: 50,
  });
  const tenants = useTenants({ limit: 200, enabled: isAdmin && !isLoading });

  if (!isLoading && !isAdmin) {
    return (
      <div className="space-y-6 p-8">
        <Card>
          <CardHeader>
            <CardTitle>Admin Access Required</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Settings for user management and audit inspection are only available to Sphere admins.
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-muted-foreground mt-1">
          User management, webhooks, and audit log
        </p>
      </div>

      <Tabs defaultValue="users">
        <TabsList>
          <TabsTrigger value="users">Users</TabsTrigger>
          {isAdmin && <TabsTrigger value="audit-log">Audit Log</TabsTrigger>}
        </TabsList>

        <TabsContent value="users" className="mt-6">
          <UsersTable
            data={users.data}
            isLoading={users.isLoading}
            searchValue={userSearch}
            tenantFilterValue={userTenantId}
            onTenantFilterChange={(value) => {
              setUserTenantId(value);
              setUserPage(1);
            }}
            tenantOptions={tenants.data?.tenants ?? []}
            onSearchChange={(v) => {
              setUserSearch(v);
              setUserPage(1);
            }}
          />
        </TabsContent>

        {isAdmin && (
          <TabsContent value="audit-log" className="mt-6">
            <AuditLogTable
              data={auditLogs.data}
              isLoading={auditLogs.isLoading}
              page={auditPage}
              onPageChange={setAuditPage}
              resourceTypeFilter={resourceTypeFilter}
              onResourceTypeChange={(v) => {
                setResourceTypeFilter(v);
                setAuditPage(1);
              }}
              actionFilter={actionFilter}
              onActionChange={(v) => {
                setActionFilter(v);
                setAuditPage(1);
              }}
              tenantFilter={auditTenantId}
              onTenantFilterChange={(value) => {
                setAuditTenantId(value);
                setAuditPage(1);
              }}
              tenantOptions={tenants.data?.tenants ?? []}
            />
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}
