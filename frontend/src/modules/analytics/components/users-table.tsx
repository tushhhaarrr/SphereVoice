"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Plus, Search, Trash2 } from "lucide-react";
import type { TenantRecord, UserListResponse, UserProfile, UserRole } from "../types";
import { useInvitations, useInviteUser, useRevokeInvitation, useUpdateUser } from "../hooks/use-users";

interface UsersTableProps {
    data: UserListResponse | undefined;
    isLoading: boolean;
    searchValue: string;
    onSearchChange: (value: string) => void;
    tenantFilterValue?: string;
    onTenantFilterChange?: (value: string) => void;
    tenantOptions?: TenantRecord[];
}

const ROLE_BADGE_VARIANTS: Record<string, string> = {
    admin: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
    developer: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
    read_only: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200",
    client_user: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
};

function RoleBadge({ role }: { role: string }) {
    return (
        <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${ROLE_BADGE_VARIANTS[role] || ROLE_BADGE_VARIANTS.read_only
                }`}
        >
            {role.replace("_", " ")}
        </span>
    );
}

function UserRow({
    user,
    tenantOptions = [],
}: {
    user: UserProfile;
    tenantOptions?: TenantRecord[];
}) {
    const updateUser = useUpdateUser();
    const tenant = tenantOptions.find((item) => item.id === user.tenant_id);
    const [roleError, setRoleError] = useState<string | null>(null);

    const handleToggleActive = () => {
        updateUser.mutate({
            userId: user.id,
            data: { is_active: !user.is_active },
        });
    };

    const handleRoleChange = (newRole: UserRole) => {
        setRoleError(null);
        updateUser.mutate(
            { userId: user.id, data: { role: newRole } },
            { onError: (err) => setRoleError(err.message) }
        );
    };

    return (
        <TableRow>
            <TableCell>
                <div>
                    <p className="font-medium">{user.name}</p>
                    <p className="text-sm text-muted-foreground">{user.email}</p>
                </div>
            </TableCell>
            <TableCell>
                <div className="space-y-1">
                    <Select
                        value={user.role}
                        onValueChange={(v) => handleRoleChange(v as UserRole)}
                        disabled={updateUser.isPending}
                    >
                        <SelectTrigger className="w-[140px]">
                            <RoleBadge role={user.role} />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="admin">Admin</SelectItem>
                            <SelectItem value="developer">Developer</SelectItem>
                            <SelectItem value="read_only">Read Only</SelectItem>
                            <SelectItem value="client_user">Client User</SelectItem>
                        </SelectContent>
                    </Select>
                    {roleError && (
                        <p className="text-xs text-destructive">{roleError}</p>
                    )}
                </div>
            </TableCell>
            <TableCell>
                {user.tenant_id ? (
                    <div>
                        <p className="text-sm font-medium">{tenant?.name || "Unknown tenant"}</p>
                        <p className="text-xs text-muted-foreground">{user.tenant_id.slice(0, 8)}...</p>
                    </div>
                ) : (
                    <span className="text-xs text-muted-foreground">All tenants</span>
                )}
            </TableCell>
            <TableCell>
                <Switch
                    checked={user.is_active}
                    onCheckedChange={handleToggleActive}
                    aria-label={`Toggle active status for ${user.name}`}
                />
            </TableCell>
            <TableCell className="text-sm text-muted-foreground">
                {user.last_login_at
                    ? new Date(user.last_login_at).toLocaleDateString()
                    : "Never"}
            </TableCell>
            <TableCell className="text-sm text-muted-foreground">
                {new Date(user.created_at).toLocaleDateString()}
            </TableCell>
        </TableRow>
    );
}

function InviteUserDialog({ tenantOptions = [] }: { tenantOptions?: TenantRecord[] }) {
    const [open, setOpen] = useState(false);
    const [email, setEmail] = useState("");
    const [name, setName] = useState("");
    const [role, setRole] = useState<UserRole>("read_only");
    const [tenantId, setTenantId] = useState("");
    const [sentLink, setSentLink] = useState<string | null>(null);
    const inviteUser = useInviteUser();

    const handleInvite = () => {
        if (!email.trim()) return;
        inviteUser.mutate(
            {
                email: email.trim(),
                name: name.trim() || undefined,
                role,
                tenant_id: role === "client_user" ? tenantId || undefined : undefined,
            },
            {
                onSuccess: (data) => {
                    if (data.invite_link) {
                        // Dev mode: show the link so the user can copy it
                        setSentLink(data.invite_link);
                    } else {
                        setOpen(false);
                        resetForm();
                    }
                },
            }
        );
    };

    const resetForm = () => {
        setEmail("");
        setName("");
        setRole("read_only");
        setTenantId("");
        setSentLink(null);
    };

    const handleClose = (next: boolean) => {
        if (!next) resetForm();
        setOpen(next);
    };

    return (
        <Dialog open={open} onOpenChange={handleClose}>
            <DialogTrigger asChild>
                <Button size="sm">
                    <Plus className="mr-1.5 h-4 w-4" />
                    Invite User
                </Button>
            </DialogTrigger>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Invite User</DialogTitle>
                    <DialogDescription>
                        An invitation email will be sent with a secure link to set up their account.
                        New users receive the <strong>Read Only</strong> role by default — you can
                        upgrade it afterwards.
                    </DialogDescription>
                </DialogHeader>

                {/* Dev-mode: show invite link after success */}
                {sentLink ? (
                    <div className="space-y-4 pt-2">
                        <div className="rounded-lg border bg-muted p-3 text-sm space-y-1">
                            <p className="font-medium text-foreground">Invitation created!</p>
                            <p className="text-muted-foreground text-xs">
                                Email sending is disabled (dev mode). Share this link manually:
                            </p>
                            <p className="break-all font-mono text-xs text-primary select-all">
                                {sentLink}
                            </p>
                        </div>
                        <Button className="w-full" onClick={() => { setOpen(false); resetForm(); }}>
                            Done
                        </Button>
                    </div>
                ) : (
                    <div className="space-y-4 pt-2">
                        <div className="space-y-2">
                            <label htmlFor="invite-email" className="text-sm font-medium">
                                Email <span className="text-destructive">*</span>
                            </label>
                            <Input
                                id="invite-email"
                                type="email"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                placeholder="user@example.com"
                            />
                        </div>
                        <div className="space-y-2">
                            <label htmlFor="invite-name" className="text-sm font-medium">
                                Name <span className="text-muted-foreground font-normal">(optional)</span>
                            </label>
                            <Input
                                id="invite-name"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                placeholder="Full name (pre-filled for the user)"
                            />
                        </div>
                        <div className="space-y-2">
                            <label htmlFor="invite-role" className="text-sm font-medium">Role</label>
                            <Select
                                value={role}
                                onValueChange={(v) => {
                                    const nextRole = v as UserRole;
                                    setRole(nextRole);
                                    if (nextRole !== "client_user") setTenantId("");
                                }}
                            >
                                <SelectTrigger id="invite-role">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="read_only">Read Only (default)</SelectItem>
                                    <SelectItem value="developer">Developer</SelectItem>
                                    <SelectItem value="admin">Admin</SelectItem>
                                    <SelectItem value="client_user">Client User</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                        {role === "client_user" && (
                            <div className="space-y-2">
                                <label htmlFor="invite-tenant" className="text-sm font-medium">Tenant</label>
                                <Select
                                    value={tenantId || "none"}
                                    onValueChange={(v) => setTenantId(v === "none" ? "" : v)}
                                >
                                    <SelectTrigger id="invite-tenant">
                                        <SelectValue placeholder="Select a tenant" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="none">Select a tenant</SelectItem>
                                        {tenantOptions.map((tenant) => (
                                            <SelectItem key={tenant.id} value={tenant.id}>
                                                {tenant.name}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        )}
                        <Button
                            onClick={handleInvite}
                            disabled={
                                inviteUser.isPending ||
                                !email.trim() ||
                                (role === "client_user" && !tenantId)
                            }
                            className="w-full"
                        >
                            {inviteUser.isPending ? "Sending invite…" : "Send invitation"}
                        </Button>
                        {inviteUser.isError && (
                            <p className="text-sm text-destructive">{inviteUser.error.message}</p>
                        )}
                    </div>
                )}
            </DialogContent>
        </Dialog>
    );
}

function PendingInvitesTable({ tenantOptions = [] }: { tenantOptions?: TenantRecord[] }) {
    const { data, isLoading } = useInvitations();
    const revokeInvitation = useRevokeInvitation();
    const [revokingId, setRevokingId] = useState<string | null>(null);

    const handleRevoke = (id: string) => {
        setRevokingId(id);
        revokeInvitation.mutate(id, {
            onSettled: () => setRevokingId(null),
        });
    };

    if (isLoading) {
        return (
            <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, i) => (
                    <div key={i} className="h-14 animate-pulse rounded bg-muted" />
                ))}
            </div>
        );
    }

    if (!data || data.invitations.length === 0) {
        return (
            <div className="flex h-40 items-center justify-center text-muted-foreground">
                No pending invitations.
            </div>
        );
    }

    return (
        <div className="rounded-md border">
            <Table>
                <TableHeader>
                    <TableRow>
                        <TableHead>Email</TableHead>
                        <TableHead>Role</TableHead>
                        <TableHead>Tenant</TableHead>
                        <TableHead>Expires</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead className="w-16" />
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {data.invitations.map((inv) => {
                        const tenant = tenantOptions.find((t) => t.id === inv.tenant_id);
                        return (
                            <TableRow key={inv.id}>
                                <TableCell>
                                    <div>
                                        <p className="font-medium">{inv.email}</p>
                                        {inv.name && (
                                            <p className="text-sm text-muted-foreground">{inv.name}</p>
                                        )}
                                    </div>
                                </TableCell>
                                <TableCell>
                                    <RoleBadge role={inv.role} />
                                </TableCell>
                                <TableCell>
                                    {inv.tenant_id ? (
                                        <span className="text-sm">{tenant?.name || inv.tenant_id.slice(0, 8) + "…"}</span>
                                    ) : (
                                        <span className="text-xs text-muted-foreground">—</span>
                                    )}
                                </TableCell>
                                <TableCell className="text-sm text-muted-foreground">
                                    {new Date(inv.expires_at).toLocaleDateString()}
                                </TableCell>
                                <TableCell>
                                    {inv.is_expired ? (
                                        <Badge variant="destructive" className="text-xs">Expired</Badge>
                                    ) : (
                                        <Badge variant="secondary" className="text-xs">Pending</Badge>
                                    )}
                                </TableCell>
                                <TableCell>
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        className="h-8 w-8 text-muted-foreground hover:text-destructive"
                                        disabled={revokingId === inv.id}
                                        onClick={() => handleRevoke(inv.id)}
                                        aria-label="Revoke invitation"
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </Button>
                                </TableCell>
                            </TableRow>
                        );
                    })}
                </TableBody>
            </Table>
        </div>
    );
}

export function UsersTable({
    data,
    isLoading,
    searchValue,
    onSearchChange,
    tenantFilterValue = "",
    onTenantFilterChange,
    tenantOptions = [],
}: UsersTableProps) {
    const { data: invitesData } = useInvitations();
    const pendingCount = invitesData?.invitations.filter((i) => !i.is_expired).length ?? 0;

    return (
        <Tabs defaultValue="users" className="space-y-4">
            <div className="flex items-center justify-between gap-4">
                <TabsList>
                    <TabsTrigger value="users">Active Users</TabsTrigger>
                    <TabsTrigger value="invites" className="gap-1.5">
                        Pending Invites
                        {pendingCount > 0 && (
                            <Badge variant="secondary" className="h-5 px-1.5 text-xs">
                                {pendingCount}
                            </Badge>
                        )}
                    </TabsTrigger>
                </TabsList>
                <InviteUserDialog tenantOptions={tenantOptions} />
            </div>

            <TabsContent value="users" className="space-y-4">
                <div className="flex flex-wrap items-center gap-3">
                    <div className="relative max-w-sm flex-1">
                        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                        <Input
                            value={searchValue}
                            onChange={(e) => onSearchChange(e.target.value)}
                            placeholder="Search by name or email..."
                            className="pl-9"
                        />
                    </div>
                    {onTenantFilterChange && (
                        <Select
                            value={tenantFilterValue || "all"}
                            onValueChange={(value) =>
                                onTenantFilterChange(value === "all" ? "" : value)
                            }
                        >
                            <SelectTrigger className="w-[220px]">
                                <SelectValue placeholder="All tenants" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">All tenants</SelectItem>
                                {tenantOptions.map((tenant) => (
                                    <SelectItem key={tenant.id} value={tenant.id}>
                                        {tenant.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    )}
                </div>

                {isLoading ? (
                    <div className="space-y-3">
                        {Array.from({ length: 5 }).map((_, i) => (
                            <div key={i} className="h-14 animate-pulse rounded bg-muted" />
                        ))}
                    </div>
                ) : !data || data.users.length === 0 ? (
                    <div className="flex h-40 items-center justify-center text-muted-foreground">
                        No users found.
                    </div>
                ) : (
                    <>
                        <div className="rounded-md border">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>User</TableHead>
                                        <TableHead>Role</TableHead>
                                        <TableHead>Tenant</TableHead>
                                        <TableHead>Active</TableHead>
                                        <TableHead>Last Login</TableHead>
                                        <TableHead>Created</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {data.users.map((user) => (
                                        <UserRow key={user.id} user={user} tenantOptions={tenantOptions} />
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                        <div className="text-sm text-muted-foreground">
                            Showing {data.users.length} of {data.total} users
                        </div>
                    </>
                )}
            </TabsContent>

            <TabsContent value="invites">
                <PendingInvitesTable tenantOptions={tenantOptions} />
            </TabsContent>
        </Tabs>
    );
}
