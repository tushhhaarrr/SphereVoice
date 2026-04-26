"use client";

/**
 * Knowledge Base detail panel.
 *
 * Shows KB info, document list with upload/add text,
 * and a search test area.
 */

import { useCallback, useRef, useState } from "react";
import {
    FileUp,
    FileText,
    Trash2,
    Upload,
    Search,
    CheckCircle,
    Clock,
    Loader2,
    ChevronDown,
    ChevronRight,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";

import {
    useKnowledgeBase,
    useKBDocuments,
    useUploadDocument,
    useAddTextDocument,
    useDeleteDocument,
    useSearchKB,
    useDocumentChunks,
} from "../hooks/use-knowledge-base";
import type { KBDocument, DocumentStatus } from "../types";
import { RoleGuard } from "@/modules/auth";

interface Props {
    kbId: string;
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

const STATUS_ICONS: Record<DocumentStatus, React.ReactNode> = {
    pending: <Clock className="h-3.5 w-3.5 text-yellow-500" />,
    processing: <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-500" />,
    processed: <CheckCircle className="h-3.5 w-3.5 text-green-500" />,
    failed: <span className="h-3.5 w-3.5 text-destructive">✕</span>,
};

export function KBDetailPanel({ kbId, open, onOpenChange }: Props) {
    const { data: kb, isLoading: kbLoading } = useKnowledgeBase(kbId);
    const { data: docsData, isLoading: docsLoading } = useKBDocuments(kbId);
    const uploadMutation = useUploadDocument(kbId);
    const addTextMutation = useAddTextDocument(kbId);
    const deleteMutation = useDeleteDocument(kbId);

    // File upload state
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [isDragOver, setIsDragOver] = useState(false);

    // Text document state
    const [textName, setTextName] = useState("");
    const [textContent, setTextContent] = useState("");

    // Expanded chunk viewer state
    const [expandedDocId, setExpandedDocId] = useState<string | null>(null);
    const { data: chunksData, isLoading: chunksLoading } = useDocumentChunks(
        kbId,
        expandedDocId
    );

    // Search state
    const [searchQuery, setSearchQuery] = useState("");
    const [activeSearch, setActiveSearch] = useState("");
    const { data: searchResults, isLoading: searchLoading } = useSearchKB(
        kbId,
        activeSearch
    );

    const handleFileUpload = useCallback(
        async (files: FileList | null) => {
            if (!files) return;
            for (const file of Array.from(files)) {
                try {
                    await uploadMutation.mutateAsync(file);
                } catch {
                    // Error handled by mutation
                }
            }
        },
        [uploadMutation]
    );

    const handleDrop = useCallback(
        (e: React.DragEvent) => {
            e.preventDefault();
            setIsDragOver(false);
            handleFileUpload(e.dataTransfer.files);
        },
        [handleFileUpload]
    );

    const handleAddText = async () => {
        if (!textName.trim() || !textContent.trim()) return;
        try {
            await addTextMutation.mutateAsync({
                name: textName,
                content: textContent,
            });
            setTextName("");
            setTextContent("");
        } catch {
            // Error handled
        }
    };

    if (kbLoading) {
        return (
            <Dialog open={open} onOpenChange={onOpenChange}>
                <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
                    <div className="flex items-center justify-center p-8">Loading...</div>
                </DialogContent>
            </Dialog>
        );
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-3xl max-h-[85vh] overflow-hidden flex flex-col">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <FileText className="h-5 w-5" />
                        {kb?.name || "Knowledge Base"}
                    </DialogTitle>
                    <DialogDescription>
                        {kb?.description || "Manage documents and test search."}
                    </DialogDescription>
                </DialogHeader>

                <Tabs defaultValue="documents" className="flex-1 overflow-hidden flex flex-col">
                    <TabsList>
                        <TabsTrigger value="documents">
                            Documents ({docsData?.total ?? 0})
                        </TabsTrigger>
                        <TabsTrigger value="upload">Upload</TabsTrigger>
                        <TabsTrigger value="search">Search</TabsTrigger>
                    </TabsList>

                    {/* Documents Tab */}
                    <TabsContent value="documents" className="flex-1 overflow-auto">
                        {docsLoading ? (
                            <div className="flex items-center justify-center p-8 text-muted-foreground">
                                Loading documents...
                            </div>
                        ) : !docsData || docsData.items.length === 0 ? (
                            <div className="flex flex-col items-center justify-center p-8 text-center">
                                <FileUp className="h-8 w-8 text-muted-foreground mb-2" />
                                <p className="text-sm text-muted-foreground">
                                    No documents yet. Upload files or add text to get started.
                                </p>
                            </div>
                        ) : (
                            <div className="rounded-md border">
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>Name</TableHead>
                                            <TableHead>Type</TableHead>
                                            <TableHead>Chunks</TableHead>
                                            <TableHead>Status</TableHead>
                                            <TableHead className="w-[60px]" />
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {docsData.items.map((doc: KBDocument) => (
                                            <>
                                            <TableRow
                                                key={doc.id}
                                                className="cursor-pointer hover:bg-muted/50"
                                                onClick={() =>
                                                    setExpandedDocId(
                                                        expandedDocId === doc.id ? null : doc.id
                                                    )
                                                }
                                            >
                                                <TableCell className="font-medium">
                                                    <div className="flex items-center gap-1.5">
                                                        {expandedDocId === doc.id
                                                            ? <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                                                            : <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />}
                                                        {doc.name}
                                                    </div>
                                                </TableCell>
                                                <TableCell>
                                                    <Badge variant="secondary">{doc.type}</Badge>
                                                </TableCell>
                                                <TableCell>{doc.chunk_count || "—"}</TableCell>
                                                <TableCell>
                                                    <div className="flex items-center gap-1.5">
                                                        {STATUS_ICONS[doc.status]}
                                                        <span className="text-sm capitalize">
                                                            {doc.status}
                                                        </span>
                                                    </div>
                                                </TableCell>
                                                <TableCell>
                                                    <RoleGuard roles={["admin", "developer"]}>
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                deleteMutation.mutate(doc.id);
                                                            }}
                                                            disabled={deleteMutation.isPending}
                                                        >
                                                            <Trash2 className="h-4 w-4 text-destructive" />
                                                        </Button>
                                                    </RoleGuard>
                                                </TableCell>
                                            </TableRow>
                                            {expandedDocId === doc.id && (
                                                <TableRow key={`${doc.id}-chunks`}>
                                                    <TableCell colSpan={5} className="bg-muted/30 p-0">
                                                        <div className="px-6 py-3 space-y-2">
                                                            {chunksLoading ? (
                                                                <div className="flex items-center gap-2 text-sm text-muted-foreground py-2">
                                                                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                                                    Loading chunks…
                                                                </div>
                                                            ) : !chunksData?.items.length ? (
                                                                <p className="text-sm text-muted-foreground py-2">No chunks yet — still processing.</p>
                                                            ) : (
                                                                chunksData.items.map((chunk) => (
                                                                    <div
                                                                        key={chunk.id}
                                                                        className="rounded border bg-background p-3"
                                                                    >
                                                                        <p className="text-xs font-mono text-muted-foreground mb-1">Chunk {chunk.chunk_index + 1}</p>
                                                                        <p className="text-sm whitespace-pre-wrap leading-relaxed">{chunk.chunk_text}</p>
                                                                    </div>
                                                                ))
                                                            )}
                                                        </div>
                                                    </TableCell>
                                                </TableRow>
                                            )}
                                            </>
                                        ))}
                                    </TableBody>
                                </Table>
                            </div>
                        )}
                    </TabsContent>

                    {/* Upload Tab */}
                    <TabsContent value="upload" className="flex-1 overflow-auto space-y-6">
                        {/* Drag & Drop Upload */}
                        <div>
                            <Label className="text-sm font-medium">File Upload</Label>
                            <div
                                className={`mt-2 flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors ${isDragOver
                                        ? "border-primary bg-primary/5"
                                        : "border-muted-foreground/25 hover:border-muted-foreground/50"
                                    }`}
                                onDragOver={(e) => {
                                    e.preventDefault();
                                    setIsDragOver(true);
                                }}
                                onDragLeave={() => setIsDragOver(false)}
                                onDrop={handleDrop}
                            >
                                <Upload className="h-8 w-8 text-muted-foreground mb-2" />
                                <p className="text-sm text-muted-foreground mb-1">
                                    Drag & drop files here, or click to browse
                                </p>
                                <p className="text-xs text-muted-foreground">
                                    Supported: PDF, DOCX, TXT, MD (max 100MB)
                                </p>
                                <input
                                    ref={fileInputRef}
                                    type="file"
                                    accept=".pdf,.docx,.txt,.md,.text"
                                    multiple
                                    className="hidden"
                                    onChange={(e) => handleFileUpload(e.target.files)}
                                />
                                <Button
                                    variant="outline"
                                    size="sm"
                                    className="mt-3"
                                    onClick={() => fileInputRef.current?.click()}
                                    disabled={uploadMutation.isPending}
                                >
                                    {uploadMutation.isPending ? (
                                        <>
                                            <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                                            Uploading...
                                        </>
                                    ) : (
                                        "Choose Files"
                                    )}
                                </Button>
                            </div>
                        </div>

                        <Separator />

                        {/* Add Text Document */}
                        <div className="space-y-3">
                            <Label className="text-sm font-medium">Add Text Content</Label>
                            <Input
                                placeholder="Document name"
                                value={textName}
                                onChange={(e) => setTextName(e.target.value)}
                            />
                            <Textarea
                                placeholder="Paste or type your content here..."
                                rows={6}
                                value={textContent}
                                onChange={(e) => setTextContent(e.target.value)}
                            />
                            <Button
                                size="sm"
                                onClick={handleAddText}
                                disabled={
                                    !textName.trim() ||
                                    !textContent.trim() ||
                                    addTextMutation.isPending
                                }
                            >
                                {addTextMutation.isPending ? "Adding..." : "Add Text Document"}
                            </Button>
                        </div>
                    </TabsContent>

                    {/* Search Tab */}
                    <TabsContent value="search" className="flex-1 overflow-auto space-y-4">
                        <div className="flex items-center gap-2">
                            <div className="relative flex-1">
                                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                                <Input
                                    placeholder="Search this knowledge base..."
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    onKeyDown={(e) => {
                                        if (e.key === "Enter") setActiveSearch(searchQuery);
                                    }}
                                    className="pl-9"
                                />
                            </div>
                            <Button
                                onClick={() => setActiveSearch(searchQuery)}
                                disabled={!searchQuery.trim() || searchLoading}
                            >
                                {searchLoading ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                    "Search"
                                )}
                            </Button>
                        </div>

                        {searchResults && searchResults.results.length > 0 ? (
                            <div className="space-y-3">
                                {searchResults.results.map((result, idx) => (
                                    <div
                                        key={`${result.document_id}-${idx}`}
                                        className="rounded-lg border p-4 space-y-2"
                                    >
                                        <div className="flex items-center justify-between">
                                            <span className="text-sm font-medium">
                                                {result.document_name}
                                            </span>
                                            <Badge variant="outline">
                                                {(result.similarity * 100).toFixed(1)}% match
                                            </Badge>
                                        </div>
                                        <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                                            {result.chunk_text}
                                        </p>
                                    </div>
                                ))}
                            </div>
                        ) : activeSearch && !searchLoading ? (
                            <div className="flex items-center justify-center p-8 text-sm text-muted-foreground">
                                No results found for &ldquo;{activeSearch}&rdquo;
                            </div>
                        ) : null}
                    </TabsContent>
                </Tabs>
            </DialogContent>
        </Dialog>
    );
}
