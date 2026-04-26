"use client";

import { useState, useCallback } from "react";
import { Upload, FileText, Loader2, AlertTriangle, CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";

interface StepCsvUploadProps {
    campaignId: string;
    tenantId?: string;
    onLoadComplete: (loaded: number, skipped: number) => void;
}

const SphereVoice_FIELDS = [
    { key: "phone_number", label: "Phone Number", required: true },
    { key: "name", label: "Name", required: false },
    { key: "email", label: "Email", required: false },
    { key: "company", label: "Company", required: false },
    { key: "city", label: "City", required: false },
] as const;

type UploadState = "idle" | "uploading" | "mapping" | "loading" | "done" | "error";

interface CsvPreview {
    columns: string[];
    row_count: number;
    sample_rows: Record<string, string>[];
}

interface LoadResult {
    loaded: number;
    skipped: number;
    invalid_rows: { row_index: number; reason: string }[];
}

export function StepCsvUpload({ campaignId, tenantId, onLoadComplete }: StepCsvUploadProps) {
    const [state, setState] = useState<UploadState>("idle");
    const [preview, setPreview] = useState<CsvPreview | null>(null);
    const [columnMapping, setColumnMapping] = useState<Record<string, string>>({});
    const [loadResult, setLoadResult] = useState<LoadResult | null>(null);
    const [errorMsg, setErrorMsg] = useState("");
    const [fileName, setFileName] = useState("");

    const handleFileDrop = useCallback(
        async (file: File) => {
            if (!file.name.endsWith(".csv")) {
                setErrorMsg("Please upload a .csv file");
                setState("error");
                return;
            }

            setState("uploading");
            setErrorMsg("");
            setFileName(file.name);

            try {
                const { fetchWithAuth } = await import("@/lib/api-client");
                const formData = new FormData();
                formData.append("file", file);

                const qs = tenantId ? `?tenant_id=${tenantId}` : "";

                const res = await fetchWithAuth(
                    `/api/v1/campaigns/${campaignId}/upload-csv${qs}`,
                    { method: "POST", body: formData }
                );
                if (!res.ok) {
                    const err = await res.json().catch(() => ({}));
                    throw new Error(
                        (err as { detail?: string }).detail ?? "Failed to upload CSV"
                    );
                }
                const data: CsvPreview = await res.json();
                setPreview(data);

                // Auto-map obvious columns
                const autoMap: Record<string, string> = {};
                for (const field of SphereVoice_FIELDS) {
                    const match = data.columns.find(
                        (col) =>
                            col.toLowerCase().replace(/[_\s-]/g, "") ===
                            field.key.replace(/_/g, "")
                    );
                    if (match) autoMap[field.key] = match;
                }
                // phone fallback
                if (!autoMap.phone_number) {
                    const phoneCol = data.columns.find(
                        (col) =>
                            col.toLowerCase().includes("phone") ||
                            col.toLowerCase().includes("mobile") ||
                            col.toLowerCase().includes("number")
                    );
                    if (phoneCol) autoMap.phone_number = phoneCol;
                }
                setColumnMapping(autoMap);
                setState("mapping");
            } catch (err) {
                setErrorMsg(err instanceof Error ? err.message : "Upload failed");
                setState("error");
            }
        },
        [campaignId, tenantId]
    );

    const handleLoadContacts = useCallback(async () => {
        if (!columnMapping.phone_number) return;

        setState("loading");
        try {
            const { fetchWithAuth } = await import("@/lib/api-client");
            const qs = tenantId ? `?tenant_id=${tenantId}` : "";
            const res = await fetchWithAuth(
                `/api/v1/campaigns/${campaignId}/load-from-csv${qs}`,
                {
                    method: "POST",
                    body: JSON.stringify({ column_mapping: columnMapping }),
                }
            );
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(
                    (err as { detail?: string }).detail ?? "Failed to load contacts"
                );
            }
            const data: LoadResult = await res.json();
            setLoadResult(data);
            setState("done");
            onLoadComplete(data.loaded, data.skipped);
        } catch (err) {
            setErrorMsg(err instanceof Error ? err.message : "Load failed");
            setState("error");
        }
    }, [campaignId, columnMapping, onLoadComplete]);

    return (
        <div className="space-y-6">
            <div>
                <h3 className="text-lg font-semibold">Upload CSV</h3>
                <p className="text-sm text-muted-foreground">
                    Upload a CSV file with contact phone numbers. Max 10,000 rows, 10 MB.
                </p>
            </div>

            {/* Drop zone */}
            {(state === "idle" || state === "error") && (
                <label className="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-muted-foreground/25 p-8 transition-colors hover:border-primary/50 hover:bg-muted/30">
                    <Upload className="mb-3 h-8 w-8 text-muted-foreground/60" />
                    <span className="text-sm font-medium">
                        Click to select or drag & drop a CSV file
                    </span>
                    <span className="mt-1 text-xs text-muted-foreground">
                        .csv files only
                    </span>
                    <input
                        type="file"
                        accept=".csv"
                        className="hidden"
                        onChange={(e) => {
                            const file = e.target.files?.[0];
                            if (file) handleFileDrop(file);
                        }}
                    />
                </label>
            )}

            {/* Uploading */}
            {state === "uploading" && (
                <div className="flex items-center gap-3 rounded-lg border p-4">
                    <Loader2 className="h-5 w-5 animate-spin text-primary" />
                    <div>
                        <p className="text-sm font-medium">Uploading {fileName}...</p>
                        <p className="text-xs text-muted-foreground">Parsing columns and rows</p>
                    </div>
                </div>
            )}

            {/* Error */}
            {state === "error" && errorMsg && (
                <div className="flex items-start gap-2 rounded-md border border-destructive/20 bg-destructive/5 p-3">
                    <AlertTriangle className="mt-0.5 h-4 w-4 text-destructive" />
                    <p className="text-sm text-destructive">{errorMsg}</p>
                </div>
            )}

            {/* Column mapping */}
            {state === "mapping" && preview && (
                <div className="space-y-4">
                    <div className="flex items-center gap-2">
                        <FileText className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm">
                            <strong>{fileName}</strong> — {preview.row_count} rows,{" "}
                            {preview.columns.length} columns
                        </span>
                    </div>

                    <div className="space-y-3 rounded-lg border p-4">
                        <p className="text-sm font-medium">Map CSV columns to SphereVoice fields</p>
                        {SphereVoice_FIELDS.map((field) => (
                            <div key={field.key} className="grid grid-cols-2 items-center gap-3">
                                <Label className="text-sm">
                                    {field.label}
                                    {field.required && <span className="ml-1 text-destructive">*</span>}
                                </Label>
                                <Select
                                    value={columnMapping[field.key] ?? "__none__"}
                                    onValueChange={(v) =>
                                        setColumnMapping((prev) => ({
                                            ...prev,
                                            [field.key]: v === "__none__" ? "" : v,
                                        }))
                                    }
                                >
                                    <SelectTrigger>
                                        <SelectValue placeholder="Select column" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="__none__">— Skip —</SelectItem>
                                        {preview.columns.map((col) => (
                                            <SelectItem key={col} value={col}>
                                                {col}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        ))}
                    </div>

                    {/* Preview table */}
                    {preview.sample_rows.length > 0 && (
                        <div className="space-y-2">
                            <p className="text-sm font-medium text-muted-foreground">
                                Preview (first {preview.sample_rows.length} rows)
                            </p>
                            <div className="overflow-x-auto rounded-md border">
                                <table className="w-full text-xs">
                                    <thead>
                                        <tr className="border-b bg-muted/50">
                                            {preview.columns.map((col) => (
                                                <th key={col} className="px-3 py-2 text-left font-medium">
                                                    {col}
                                                </th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {preview.sample_rows.map((row, idx) => (
                                            <tr key={idx} className="border-b last:border-0">
                                                {preview.columns.map((col) => (
                                                    <td key={col} className="px-3 py-1.5 text-muted-foreground">
                                                        {row[col] ?? ""}
                                                    </td>
                                                ))}
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}

                    <Button
                        onClick={handleLoadContacts}
                        disabled={!columnMapping.phone_number}
                    >
                        Load {preview.row_count} Contacts
                    </Button>
                </div>
            )}

            {/* Loading */}
            {state === "loading" && (
                <div className="flex items-center gap-3 rounded-lg border p-4">
                    <Loader2 className="h-5 w-5 animate-spin text-primary" />
                    <p className="text-sm">Loading contacts into campaign...</p>
                </div>
            )}

            {/* Done */}
            {state === "done" && loadResult && (
                <div className="space-y-3">
                    <div className="flex items-start gap-2 rounded-md border border-green-200 bg-green-50 p-3 dark:border-green-800 dark:bg-green-950">
                        <CheckCircle className="mt-0.5 h-4 w-4 text-green-600 dark:text-green-400" />
                        <div className="text-sm">
                            <p className="font-medium text-green-800 dark:text-green-200">
                                {loadResult.loaded} contacts loaded
                            </p>
                            {loadResult.skipped > 0 && (
                                <p className="text-green-700 dark:text-green-300">
                                    {loadResult.skipped} duplicates skipped
                                </p>
                            )}
                        </div>
                    </div>

                    {loadResult.invalid_rows.length > 0 && (
                        <div className="space-y-1">
                            <p className="text-sm font-medium text-amber-700 dark:text-amber-400">
                                {loadResult.invalid_rows.length} invalid rows
                            </p>
                            <div className="max-h-32 overflow-y-auto rounded-md border p-2">
                                {loadResult.invalid_rows.slice(0, 20).map((row) => (
                                    <p key={row.row_index} className="text-xs text-muted-foreground">
                                        Row {row.row_index + 1}: {row.reason}
                                    </p>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
