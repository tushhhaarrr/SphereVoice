import { TenantWorkspaceGuard } from "@/components/layout/tenant-workspace-guard";
import { TenantWorkspaceShell } from "@/components/layout/tenant-workspace-shell";

export default async function WorkspaceLayout({
    children,
    params,
}: {
    children: React.ReactNode;
    params: Promise<{ tenantId: string }>;
}) {
    const { tenantId } = await params;

    return (
        <>
            <TenantWorkspaceGuard tenantId={tenantId} />
            <TenantWorkspaceShell tenantId={tenantId}>{children}</TenantWorkspaceShell>
        </>
    );
}