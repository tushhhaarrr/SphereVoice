"use client";

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TenantsTable, useTenants } from "@/modules/analytics";
import { useAuth } from "@/modules/auth";

export default function AgencyTenantsPage() {
    const { isAdmin, isLoading } = useAuth();
    const [search, setSearch] = useState("");
    const [status, setStatus] = useState("all");

    const tenants = useTenants({
        enabled: isAdmin && !isLoading,
        search: search || undefined,
        status: status !== "all" ? (status as "active" | "inactive" | "suspended") : undefined,
        limit: 100,
    });

    if (!isLoading && !isAdmin) {
        return (
            <div className="space-y-6 p-8">
                <Card>
                    <CardHeader>
                        <CardTitle>Admin Access Required</CardTitle>
                    </CardHeader>
                    <CardContent className="text-sm text-muted-foreground">
                        Agency tenant management is restricted to Sphere admins.
                    </CardContent>
                </Card>
            </div>
        );
    }

    return (
        <div className="space-y-6 p-8">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                <div>
                    <h1 className="text-2xl font-bold">Tenant Directory</h1>
                    <p className="mt-1 text-muted-foreground">
                        Search the client portfolio, review tenant status, and route operators into isolated workspaces.
                    </p>
                </div>
                <Button asChild variant="outline">
                    <Link href="/agency/onboarding">Open Onboarding Queue</Link>
                </Button>
            </div>

            <TenantsTable
                data={tenants.data}
                isLoading={tenants.isLoading}
                searchValue={search}
                onSearchChange={setSearch}
                statusValue={status}
                onStatusChange={setStatus}
            />
        </div>
    );
}