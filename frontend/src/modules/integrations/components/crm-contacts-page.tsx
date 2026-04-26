"use client";

/**
 * CrmContactsPage — browse and search Zoho CRM contacts / leads with
 * click-to-call functionality.  Only available when the tenant has an
 * active Zoho CRM integration.
 */

import { useCallback, useState } from "react";
import { useParams } from "next/navigation";
import {
    Building2,
    Calendar,
    CheckSquare,
    ChevronLeft,
    ChevronRight,
    FileText,
    Loader2,
    Mail,
    Megaphone,
    Phone,
    PhoneCall,
    Search,
    StickyNote,
    User,
    Users,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";

import { useCrmIntegrations } from "../hooks/use-integrations";
import {
    useCallFromCrm,
    useCrmAccounts,
    useCrmCalls,
    useCrmCampaigns,
    useCrmContacts,
    useCrmDeals,
    useCrmLeads,
    useCrmMeetings,
    useCrmNotes,
    useCrmTasks,
} from "../hooks/use-crm-data";
import type { ZohoRecord } from "../types";

// ── Sub-components ──────────────────────────────────────────

function EmptyState({ message }: { message: string }) {
    return (
        <div className="flex flex-col items-center justify-center py-12 text-center">
            <Users className="h-10 w-10 text-muted-foreground/40 mb-3" />
            <p className="text-sm text-muted-foreground">{message}</p>
        </div>
    );
}

function ContactRow({
    record,
    onCall,
}: {
    record: ZohoRecord;
    onCall: (record: ZohoRecord) => void;
}) {
    const name =
        record.Full_Name ||
        [record.First_Name, record.Last_Name].filter(Boolean).join(" ") ||
        "—";

    return (
        <TableRow className="group">
            <TableCell>
                <div className="flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary text-xs font-medium shrink-0">
                        {(record.First_Name?.[0] || record.Last_Name?.[0] || "?").toUpperCase()}
                    </div>
                    <div className="min-w-0">
                        <p className="font-medium text-sm truncate">{name}</p>
                        {record.Title && (
                            <p className="text-xs text-muted-foreground truncate">
                                {record.Title}
                            </p>
                        )}
                    </div>
                </div>
            </TableCell>
            <TableCell>
                {record.Company && (
                    <div className="flex items-center gap-1 text-sm">
                        <Building2 className="h-3 w-3 text-muted-foreground shrink-0" />
                        <span className="truncate">{record.Company}</span>
                    </div>
                )}
            </TableCell>
            <TableCell>
                {record.Email && (
                    <div className="flex items-center gap-1 text-sm">
                        <Mail className="h-3 w-3 text-muted-foreground shrink-0" />
                        <span className="truncate">{record.Email}</span>
                    </div>
                )}
            </TableCell>
            <TableCell>
                <div className="space-y-0.5">
                    {record.Phone && (
                        <div className="flex items-center gap-1 text-sm">
                            <Phone className="h-3 w-3 text-muted-foreground shrink-0" />
                            <span>{record.Phone}</span>
                        </div>
                    )}
                    {record.Mobile && record.Mobile !== record.Phone && (
                        <div className="flex items-center gap-1 text-sm text-muted-foreground">
                            <Phone className="h-3 w-3 shrink-0" />
                            <span>{record.Mobile}</span>
                        </div>
                    )}
                </div>
            </TableCell>
            <TableCell>
                {record.Lead_Status && (
                    <Badge variant="secondary" className="text-xs">
                        {record.Lead_Status}
                    </Badge>
                )}
                {record.Stage && (
                    <Badge variant="outline" className="text-xs">
                        {record.Stage}
                    </Badge>
                )}
            </TableCell>
            <TableCell className="text-right">
                {(record.Phone || record.Mobile) && (
                    <Button
                        size="sm"
                        variant="ghost"
                        className="gap-1 opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={() => onCall(record)}
                    >
                        <PhoneCall className="h-3.5 w-3.5" />
                        Call
                    </Button>
                )}
            </TableCell>
        </TableRow>
    );
}

// ── Main page component ─────────────────────────────────────

export function CrmContactsPage() {
    const params = useParams<{ tenantId: string }>();
    const tenantId = params.tenantId;
    const { data: integrationsData } = useCrmIntegrations(tenantId);
    const zohoIntegration = integrationsData?.integrations.find(
        (i) => i.provider === "zoho_crm" && i.status === "connected"
    );
    const isConnected = !!zohoIntegration;

    const [tab, setTab] = useState<"contacts" | "leads" | "deals" | "accounts" | "tasks" | "calls" | "notes" | "meetings" | "campaigns">("contacts");
    const [search, setSearch] = useState("");
    const [debouncedSearch, setDebouncedSearch] = useState("");
    const [page, setPage] = useState(1);

    // Click-to-call state
    const [callDialog, setCallDialog] = useState<{
        record: ZohoRecord;
        module: string;
    } | null>(null);
    const [selectedAgentId, setSelectedAgentId] = useState<string>("");
    const callFromCrm = useCallFromCrm(tenantId);

    // Debounce search input
    const handleSearch = useCallback(
        (value: string) => {
            setSearch(value);
            setPage(1);
            // Simple debounce via timeout
            const timer = setTimeout(() => setDebouncedSearch(value), 400);
            return () => clearTimeout(timer);
        },
        []
    );

    // Data queries
    const contacts = useCrmContacts({
        page,
        search: debouncedSearch || undefined,
        tenantId,
        enabled: isConnected && tab === "contacts",
    });
    const leads = useCrmLeads({
        page,
        search: debouncedSearch || undefined,
        tenantId,
        enabled: isConnected && tab === "leads",
    });
    const deals = useCrmDeals({
        page,
        tenantId,
        enabled: isConnected && tab === "deals",
    });
    const accounts = useCrmAccounts({
        page,
        search: debouncedSearch || undefined,
        tenantId,
        enabled: isConnected && tab === "accounts",
    });
    const tasks = useCrmTasks({
        page,
        tenantId,
        enabled: isConnected && tab === "tasks",
    });
    const calls = useCrmCalls({
        page,
        tenantId,
        enabled: isConnected && tab === "calls",
    });
    const notes = useCrmNotes({
        page,
        tenantId,
        enabled: isConnected && tab === "notes",
    });
    const meetings = useCrmMeetings({
        page,
        tenantId,
        enabled: isConnected && tab === "meetings",
    });
    const campaigns = useCrmCampaigns({
        page,
        tenantId,
        enabled: isConnected && tab === "campaigns",
    });

    const currentData =
        tab === "contacts"
            ? contacts
            : tab === "leads"
                ? leads
                : tab === "accounts"
                    ? accounts
                    : tab === "tasks"
                        ? tasks
                        : tab === "calls"
                            ? calls
                            : tab === "notes"
                                ? notes
                                : tab === "meetings"
                                    ? meetings
                                    : tab === "campaigns"
                                        ? campaigns
                                        : deals;

    const records = currentData.data?.data ?? [];
    const info = currentData.data?.info ?? {};
    const hasMore = info.more_records ?? false;

    function handleCallClick(record: ZohoRecord) {
        setCallDialog({
            record,
            module: tab === "leads" ? "Leads" : "Contacts",
        });
    }

    function handleInitiateCall() {
        if (!callDialog || !selectedAgentId) return;
        callFromCrm.mutate({
            contact_id: callDialog.record.id,
            contact_module: callDialog.module,
            agent_id: selectedAgentId,
        });
    }

    if (!isConnected) {
        return (
            <div className="flex flex-col items-center justify-center py-20 text-center">
                <Users className="h-12 w-12 text-muted-foreground/30 mb-4" />
                <h2 className="text-lg font-medium mb-1">CRM not connected</h2>
                <p className="text-sm text-muted-foreground max-w-md">
                    Connect your Zoho CRM in the Integrations page to browse contacts,
                    leads, and deals here.
                </p>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header with org badge */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <Users className="h-6 w-6 text-primary" />
                    <div>
                        <h1 className="text-2xl font-semibold tracking-tight">CRM Data</h1>
                        <p className="text-sm text-muted-foreground">
                            Browse and call contacts from your Zoho CRM
                        </p>
                    </div>
                </div>
                {zohoIntegration?.org_name && (
                    <Badge variant="outline" className="gap-1">
                        <Building2 className="h-3 w-3" />
                        {zohoIntegration.org_name}
                    </Badge>
                )}
            </div>

            {/* Search + Tabs */}
            <Tabs
                value={tab}
                onValueChange={(v) => {
                    setTab(v as typeof tab);
                    setPage(1);
                }}
            >
                <div className="flex items-center justify-between gap-4">
                    <TabsList className="flex-wrap h-auto gap-1">
                        <TabsTrigger value="contacts" className="gap-1">
                            <User className="h-3.5 w-3.5" />
                            Contacts
                        </TabsTrigger>
                        <TabsTrigger value="leads" className="gap-1">
                            <Users className="h-3.5 w-3.5" />
                            Leads
                        </TabsTrigger>
                        <TabsTrigger value="deals" className="gap-1">
                            <Building2 className="h-3.5 w-3.5" />
                            Deals
                        </TabsTrigger>
                        <TabsTrigger value="accounts" className="gap-1">
                            <Building2 className="h-3.5 w-3.5" />
                            Accounts
                        </TabsTrigger>
                        <TabsTrigger value="tasks" className="gap-1">
                            <CheckSquare className="h-3.5 w-3.5" />
                            Tasks
                        </TabsTrigger>
                        <TabsTrigger value="calls" className="gap-1">
                            <Phone className="h-3.5 w-3.5" />
                            Calls
                        </TabsTrigger>
                        <TabsTrigger value="notes" className="gap-1">
                            <StickyNote className="h-3.5 w-3.5" />
                            Notes
                        </TabsTrigger>
                        <TabsTrigger value="meetings" className="gap-1">
                            <Calendar className="h-3.5 w-3.5" />
                            Meetings
                        </TabsTrigger>
                        <TabsTrigger value="campaigns" className="gap-1">
                            <Megaphone className="h-3.5 w-3.5" />
                            Campaigns
                        </TabsTrigger>
                    </TabsList>

                    {(tab === "contacts" || tab === "leads" || tab === "accounts") && (
                        <div className="relative w-72">
                            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                            <Input
                                placeholder="Search by name, email, or phone..."
                                value={search}
                                onChange={(e) => handleSearch(e.target.value)}
                                className="pl-9"
                            />
                        </div>
                    )}
                </div>

                <TabsContent value="contacts" className="mt-4">
                    <RecordsTable
                        records={records}
                        isLoading={contacts.isLoading}
                        isError={contacts.isError}
                        module="Contacts"
                        onCall={handleCallClick}
                    />
                </TabsContent>
                <TabsContent value="leads" className="mt-4">
                    <RecordsTable
                        records={records}
                        isLoading={leads.isLoading}
                        isError={leads.isError}
                        module="Leads"
                        onCall={handleCallClick}
                    />
                </TabsContent>
                <TabsContent value="deals" className="mt-4">
                    <DealsTable records={records} isLoading={deals.isLoading} />
                </TabsContent>
                <TabsContent value="accounts" className="mt-4">
                    <AccountsTable records={records} isLoading={accounts.isLoading} isError={accounts.isError} />
                </TabsContent>
                <TabsContent value="tasks" className="mt-4">
                    <TasksTable records={records} isLoading={tasks.isLoading} isError={tasks.isError} />
                </TabsContent>
                <TabsContent value="calls" className="mt-4">
                    <CallsTable records={records} isLoading={calls.isLoading} isError={calls.isError} />
                </TabsContent>
                <TabsContent value="notes" className="mt-4">
                    <NotesTable records={records} isLoading={notes.isLoading} isError={notes.isError} />
                </TabsContent>
                <TabsContent value="meetings" className="mt-4">
                    <MeetingsTable records={records} isLoading={meetings.isLoading} isError={meetings.isError} />
                </TabsContent>
                <TabsContent value="campaigns" className="mt-4">
                    <CampaignsTable records={records} isLoading={campaigns.isLoading} isError={campaigns.isError} />
                </TabsContent>
            </Tabs>

            {/* Pagination */}
            {records.length > 0 && (
                <div className="flex items-center justify-between">
                    <p className="text-xs text-muted-foreground">
                        Page {page} · {info.count ?? records.length} records
                    </p>
                    <div className="flex gap-2">
                        <Button
                            size="sm"
                            variant="outline"
                            disabled={page <= 1}
                            onClick={() => setPage((p) => Math.max(1, p - 1))}
                        >
                            <ChevronLeft className="h-4 w-4" />
                            Previous
                        </Button>
                        <Button
                            size="sm"
                            variant="outline"
                            disabled={!hasMore}
                            onClick={() => setPage((p) => p + 1)}
                        >
                            Next
                            <ChevronRight className="h-4 w-4" />
                        </Button>
                    </div>
                </div>
            )}

            {/* Click-to-call dialog */}
            <Dialog
                open={!!callDialog}
                onOpenChange={(open) => {
                    if (!open) {
                        setCallDialog(null);
                        setSelectedAgentId("");
                        callFromCrm.reset();
                    }
                }}
            >
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Call CRM Contact</DialogTitle>
                        <DialogDescription>
                            {callDialog && (
                                <>
                                    Initiate a call to{" "}
                                    <strong>
                                        {callDialog.record.Full_Name ||
                                            [callDialog.record.First_Name, callDialog.record.Last_Name]
                                                .filter(Boolean)
                                                .join(" ")}
                                    </strong>{" "}
                                    at{" "}
                                    <strong>
                                        {callDialog.record.Phone || callDialog.record.Mobile}
                                    </strong>
                                </>
                            )}
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-3 py-2">
                        <label className="text-sm font-medium">Select Agent</label>
                        <Input
                            placeholder="Paste agent ID"
                            value={selectedAgentId}
                            onChange={(e) => setSelectedAgentId(e.target.value)}
                        />
                        <p className="text-xs text-muted-foreground">
                            The agent will handle the outbound call to this contact.
                        </p>
                    </div>

                    {callFromCrm.isSuccess && (
                        <div className="rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-200">
                            Call initiated! Call ID: {callFromCrm.data.call_id}
                        </div>
                    )}
                    {callFromCrm.isError && (
                        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
                            {callFromCrm.error.message}
                        </div>
                    )}

                    <DialogFooter>
                        <Button
                            variant="outline"
                            onClick={() => {
                                setCallDialog(null);
                                callFromCrm.reset();
                            }}
                        >
                            Cancel
                        </Button>
                        <Button
                            onClick={handleInitiateCall}
                            disabled={!selectedAgentId || callFromCrm.isPending}
                            className="gap-1"
                        >
                            {callFromCrm.isPending ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                                <PhoneCall className="h-4 w-4" />
                            )}
                            Start Call
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}

// ── Records table (Contacts + Leads) ────────────────────────

function RecordsTable({
    records,
    isLoading,
    isError,
    module,
    onCall,
}: {
    records: ZohoRecord[];
    isLoading: boolean;
    isError: boolean;
    module: string;
    onCall: (record: ZohoRecord) => void;
}) {
    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        );
    }
    if (isError) {
        return (
            <EmptyState message="Failed to load records. Check your CRM connection." />
        );
    }
    if (records.length === 0) {
        return <EmptyState message={`No ${module.toLowerCase()} found.`} />;
    }

    return (
        <Card>
            <CardContent className="p-0">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead className="w-[200px]">Name</TableHead>
                            <TableHead>Company</TableHead>
                            <TableHead>Email</TableHead>
                            <TableHead>Phone</TableHead>
                            <TableHead>Status</TableHead>
                            <TableHead className="w-[80px] text-right">Action</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {records.map((r) => (
                            <ContactRow key={r.id} record={r} onCall={onCall} />
                        ))}
                    </TableBody>
                </Table>
            </CardContent>
        </Card>
    );
}

// ── Deals table ─────────────────────────────────────────────

function DealsTable({
    records,
    isLoading,
}: {
    records: ZohoRecord[];
    isLoading: boolean;
}) {
    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        );
    }
    if (records.length === 0) {
        return <EmptyState message="No deals found." />;
    }

    return (
        <Card>
            <CardContent className="p-0">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead>Deal Name</TableHead>
                            <TableHead>Stage</TableHead>
                            <TableHead>Amount</TableHead>
                            <TableHead>Closing Date</TableHead>
                            <TableHead>Owner</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {records.map((r) => (
                            <TableRow key={r.id}>
                                <TableCell className="font-medium">
                                    {r.Deal_Name || "—"}
                                </TableCell>
                                <TableCell>
                                    {r.Stage && (
                                        <Badge variant="outline" className="text-xs">
                                            {r.Stage}
                                        </Badge>
                                    )}
                                </TableCell>
                                <TableCell>
                                    {r.Amount != null
                                        ? new Intl.NumberFormat("en-US", {
                                            style: "currency",
                                            currency: "USD",
                                            maximumFractionDigits: 0,
                                        }).format(r.Amount)
                                        : "—"}
                                </TableCell>
                                <TableCell>
                                    {r.Closing_Date
                                        ? new Date(r.Closing_Date).toLocaleDateString()
                                        : "—"}
                                </TableCell>
                                <TableCell>{r.Owner?.name || "—"}</TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </CardContent>
        </Card>
    );
}

// ── Shared loading/error/empty wrapper ──────────────────────

function ModuleTableWrapper({
    children,
    isLoading,
    isError,
    isEmpty,
    module,
}: {
    children: React.ReactNode;
    isLoading: boolean;
    isError?: boolean;
    isEmpty: boolean;
    module: string;
}) {
    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        );
    }
    if (isError) {
        return <EmptyState message="Failed to load records. Check your CRM connection." />;
    }
    if (isEmpty) {
        return <EmptyState message={`No ${module.toLowerCase()} found.`} />;
    }
    return <>{children}</>;
}

// ── Accounts table ──────────────────────────────────────────

function AccountsTable({
    records,
    isLoading,
    isError,
}: {
    records: ZohoRecord[];
    isLoading: boolean;
    isError: boolean;
}) {
    return (
        <ModuleTableWrapper isLoading={isLoading} isError={isError} isEmpty={records.length === 0} module="Accounts">
            <Card>
                <CardContent className="p-0">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Account Name</TableHead>
                                <TableHead>Industry</TableHead>
                                <TableHead>Phone</TableHead>
                                <TableHead>Type</TableHead>
                                <TableHead>Revenue</TableHead>
                                <TableHead>Owner</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {records.map((r) => (
                                <TableRow key={r.id}>
                                    <TableCell className="font-medium">{r.Account_Name || "—"}</TableCell>
                                    <TableCell>{r.Industry || "—"}</TableCell>
                                    <TableCell>{r.Phone || "—"}</TableCell>
                                    <TableCell>
                                        {r.Account_Type && (
                                            <Badge variant="outline" className="text-xs">{r.Account_Type}</Badge>
                                        )}
                                    </TableCell>
                                    <TableCell>
                                        {r.Annual_Revenue != null
                                            ? new Intl.NumberFormat("en-US", {
                                                style: "currency",
                                                currency: "USD",
                                                maximumFractionDigits: 0,
                                            }).format(r.Annual_Revenue)
                                            : "—"}
                                    </TableCell>
                                    <TableCell>{r.Owner?.name || "—"}</TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>
        </ModuleTableWrapper>
    );
}

// ── Tasks table ─────────────────────────────────────────────

function TasksTable({
    records,
    isLoading,
    isError,
}: {
    records: ZohoRecord[];
    isLoading: boolean;
    isError: boolean;
}) {
    return (
        <ModuleTableWrapper isLoading={isLoading} isError={isError} isEmpty={records.length === 0} module="Tasks">
            <Card>
                <CardContent className="p-0">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Subject</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead>Priority</TableHead>
                                <TableHead>Due Date</TableHead>
                                <TableHead>Owner</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {records.map((r) => (
                                <TableRow key={r.id}>
                                    <TableCell className="font-medium">{r.Subject || "—"}</TableCell>
                                    <TableCell>
                                        {r.Status && (
                                            <Badge variant={r.Status === "Completed" ? "default" : "secondary"} className="text-xs">
                                                {r.Status}
                                            </Badge>
                                        )}
                                    </TableCell>
                                    <TableCell>
                                        {r.Priority && (
                                            <Badge variant={r.Priority === "High" ? "destructive" : "outline"} className="text-xs">
                                                {r.Priority}
                                            </Badge>
                                        )}
                                    </TableCell>
                                    <TableCell>
                                        {r.Due_Date ? new Date(r.Due_Date).toLocaleDateString() : "—"}
                                    </TableCell>
                                    <TableCell>{r.Owner?.name || "—"}</TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>
        </ModuleTableWrapper>
    );
}

// ── Calls table ─────────────────────────────────────────────

function CallsTable({
    records,
    isLoading,
    isError,
}: {
    records: ZohoRecord[];
    isLoading: boolean;
    isError: boolean;
}) {
    return (
        <ModuleTableWrapper isLoading={isLoading} isError={isError} isEmpty={records.length === 0} module="Calls">
            <Card>
                <CardContent className="p-0">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Subject</TableHead>
                                <TableHead>Type</TableHead>
                                <TableHead>Start Time</TableHead>
                                <TableHead>Duration</TableHead>
                                <TableHead>Purpose</TableHead>
                                <TableHead>Result</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {records.map((r) => (
                                <TableRow key={r.id}>
                                    <TableCell className="font-medium">{r.Subject || "—"}</TableCell>
                                    <TableCell>
                                        {r.Call_Type && (
                                            <Badge variant={r.Call_Type === "Inbound" ? "default" : "secondary"} className="text-xs">
                                                {r.Call_Type}
                                            </Badge>
                                        )}
                                    </TableCell>
                                    <TableCell>
                                        {r.Call_Start_Time
                                            ? new Date(r.Call_Start_Time).toLocaleString()
                                            : "—"}
                                    </TableCell>
                                    <TableCell>{r.Call_Duration || "—"}</TableCell>
                                    <TableCell>{r.Call_Purpose || "—"}</TableCell>
                                    <TableCell>{r.Call_Result || "—"}</TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>
        </ModuleTableWrapper>
    );
}

// ── Notes table ─────────────────────────────────────────────

function NotesTable({
    records,
    isLoading,
    isError,
}: {
    records: ZohoRecord[];
    isLoading: boolean;
    isError: boolean;
}) {
    return (
        <ModuleTableWrapper isLoading={isLoading} isError={isError} isEmpty={records.length === 0} module="Notes">
            <Card>
                <CardContent className="p-0">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Title</TableHead>
                                <TableHead className="w-[40%]">Content</TableHead>
                                <TableHead>Module</TableHead>
                                <TableHead>Owner</TableHead>
                                <TableHead>Created</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {records.map((r) => (
                                <TableRow key={r.id}>
                                    <TableCell className="font-medium">{r.Note_Title || "—"}</TableCell>
                                    <TableCell>
                                        <p className="text-sm text-muted-foreground line-clamp-2">
                                            {r.Note_Content || "—"}
                                        </p>
                                    </TableCell>
                                    <TableCell>{r.se_module || "—"}</TableCell>
                                    <TableCell>{r.Owner?.name || "—"}</TableCell>
                                    <TableCell>
                                        {r.Created_Time
                                            ? new Date(r.Created_Time).toLocaleDateString()
                                            : "—"}
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>
        </ModuleTableWrapper>
    );
}

// ── Meetings table ──────────────────────────────────────────

function MeetingsTable({
    records,
    isLoading,
    isError,
}: {
    records: ZohoRecord[];
    isLoading: boolean;
    isError: boolean;
}) {
    return (
        <ModuleTableWrapper isLoading={isLoading} isError={isError} isEmpty={records.length === 0} module="Meetings">
            <Card>
                <CardContent className="p-0">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Title</TableHead>
                                <TableHead>Start</TableHead>
                                <TableHead>End</TableHead>
                                <TableHead>Location</TableHead>
                                <TableHead>Owner</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {records.map((r) => (
                                <TableRow key={r.id}>
                                    <TableCell className="font-medium">{r.Event_Title || "—"}</TableCell>
                                    <TableCell>
                                        {r.Start_DateTime
                                            ? new Date(r.Start_DateTime).toLocaleString()
                                            : "—"}
                                    </TableCell>
                                    <TableCell>
                                        {r.End_DateTime
                                            ? new Date(r.End_DateTime).toLocaleString()
                                            : "—"}
                                    </TableCell>
                                    <TableCell>{r.Location || "—"}</TableCell>
                                    <TableCell>{r.Owner?.name || "—"}</TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>
        </ModuleTableWrapper>
    );
}

// ── Campaigns table ─────────────────────────────────────────

function CampaignsTable({
    records,
    isLoading,
    isError,
}: {
    records: ZohoRecord[];
    isLoading: boolean;
    isError: boolean;
}) {
    return (
        <ModuleTableWrapper isLoading={isLoading} isError={isError} isEmpty={records.length === 0} module="Campaigns">
            <Card>
                <CardContent className="p-0">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Campaign Name</TableHead>
                                <TableHead>Type</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead>Start Date</TableHead>
                                <TableHead>End Date</TableHead>
                                <TableHead>Expected Revenue</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {records.map((r) => (
                                <TableRow key={r.id}>
                                    <TableCell className="font-medium">{r.Campaign_Name || "—"}</TableCell>
                                    <TableCell>{r.Type || "—"}</TableCell>
                                    <TableCell>
                                        {r.Status && (
                                            <Badge variant="outline" className="text-xs">{r.Status}</Badge>
                                        )}
                                    </TableCell>
                                    <TableCell>
                                        {r.Start_Date ? new Date(r.Start_Date).toLocaleDateString() : "—"}
                                    </TableCell>
                                    <TableCell>
                                        {r.End_Date ? new Date(r.End_Date).toLocaleDateString() : "—"}
                                    </TableCell>
                                    <TableCell>
                                        {r.Expected_Revenue != null
                                            ? new Intl.NumberFormat("en-US", {
                                                style: "currency",
                                                currency: "USD",
                                                maximumFractionDigits: 0,
                                            }).format(r.Expected_Revenue)
                                            : "—"}
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>
        </ModuleTableWrapper>
    );
}
