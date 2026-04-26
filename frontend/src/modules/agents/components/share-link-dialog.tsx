"use client";

/**
 * ShareLinkDialog — Create and manage shareable demo links for an agent.
 *
 * Shows a "Share Demo" button that opens a dialog where the builder can:
 * - Create a new share link with expiry and usage limits
 * - See existing links (active)
 * - Copy the link
 * - Revoke a link
 */

import { useCallback, useState } from "react";
import { Check, Copy, ExternalLink, Link2, Loader2, Share2, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";

import {
  buildShareUrl,
  EXPIRY_OPTIONS,
  useCreateShareLink,
  useRevokeShareLink,
  useShareLinks,
} from "../hooks/use-share-links";
import type { ExpiryPreset, ShareLink } from "../types/share-links";

// ── Helpers ────────────────────────────────────────────────

function formatExpiry(expiresAt: string | null): string {
  if (!expiresAt) return "Never";
  const d = new Date(expiresAt);
  const now = new Date();
  if (d < now) return "Expired";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function isExpired(expiresAt: string | null): boolean {
  if (!expiresAt) return false;
  return new Date(expiresAt) < new Date();
}

// ── Single link row ─────────────────────────────────────────

function LinkRow({ link, agentId }: { link: ShareLink; agentId: string }) {
  const revoke = useRevokeShareLink(agentId);
  const [copied, setCopied] = useState(false);
  const url = buildShareUrl(link.token);
  const expired = !link.is_active || isExpired(link.expires_at);

  const handleCopy = useCallback(() => {
    void navigator.clipboard.writeText(url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [url]);

  return (
    <div className={`flex items-center gap-3 rounded-lg border p-3 ${expired ? "opacity-50" : ""}`}>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{link.label || "Untitled link"}</p>
        <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
          <span>Expires: {formatExpiry(link.expires_at)}</span>
          {link.max_uses !== null && (
            <span>· {link.use_count}/{link.max_uses} uses</span>
          )}
          {link.max_uses === null && (
            <span>· {link.use_count} uses</span>
          )}
        </div>
      </div>

      {expired ? (
        <Badge variant="outline" className="text-xs text-muted-foreground shrink-0">Expired</Badge>
      ) : (
        <div className="flex items-center gap-1 shrink-0">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={handleCopy}
            title="Copy link"
          >
            {copied ? (
              <Check className="h-3.5 w-3.5 text-green-500" />
            ) : (
              <Copy className="h-3.5 w-3.5" />
            )}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            asChild
            title="Open in new tab"
          >
            <a href={url} target="_blank" rel="noreferrer">
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 hover:text-destructive"
            disabled={revoke.isPending}
            onClick={() => revoke.mutate(link.id)}
            title="Revoke link"
          >
            {revoke.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Trash2 className="h-3.5 w-3.5" />
            )}
          </Button>
        </div>
      )}
    </div>
  );
}

// ── New link form ───────────────────────────────────────────

function NewLinkForm({
  agentId,
  onCreated,
}: {
  agentId: string;
  onCreated: (link: ShareLink) => void;
}) {
  const create = useCreateShareLink(agentId);
  const [label, setLabel] = useState("");
  const [expiry, setExpiry] = useState<ExpiryPreset>("15m");

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      const link = await create.mutateAsync({
        label: label.trim() || null,
        expiry,
        max_uses: null,
      });
      onCreated(link);
      setLabel("");
      setExpiry("15m");
    },
    [create, expiry, label, onCreated],
  );

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="space-y-1.5">
        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Label (optional)
        </label>
        <input
          type="text"
          placeholder="e.g. Client demo — Acme Corp"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          maxLength={255}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </div>

      <div className="space-y-1.5">
        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Link expires in
        </label>
        <div className="flex flex-wrap gap-2">
          {EXPIRY_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setExpiry(opt.value)}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                expiry === opt.value
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border bg-muted/50 text-muted-foreground hover:border-primary/50 hover:bg-muted"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <Button type="submit" className="w-full" disabled={create.isPending}>
        {create.isPending ? (
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        ) : (
          <Link2 className="mr-2 h-4 w-4" />
        )}
        Generate link
      </Button>

      {create.isError && (
        <p className="text-xs text-destructive">{(create.error as Error).message}</p>
      )}
    </form>
  );
}

// ── Newly created link display ──────────────────────────────

function CreatedLinkBanner({ link }: { link: ShareLink }) {
  const [copied, setCopied] = useState(false);
  const url = buildShareUrl(link.token);

  const handleCopy = () => {
    void navigator.clipboard.writeText(url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className="rounded-lg border border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950 p-3">
      <p className="mb-2 text-xs font-medium text-green-700 dark:text-green-300">
        ✓ Link created! Share this URL with your client:
      </p>
      <div className="flex items-center gap-2">
        <code className="min-w-0 flex-1 truncate rounded bg-background px-2 py-1 text-xs text-foreground">
          {url}
        </code>
        <Button
          variant="outline"
          size="sm"
          className="shrink-0"
          onClick={handleCopy}
        >
          {copied ? (
            <><Check className="mr-1 h-3 w-3 text-green-500" />Copied!</>
          ) : (
            <><Copy className="mr-1 h-3 w-3" />Copy</>
          )}
        </Button>
      </div>
    </div>
  );
}

// ── Main dialog ─────────────────────────────────────────────

interface ShareLinkDialogProps {
  agentId: string;
  agentName: string;
}

export function ShareLinkDialog({ agentId, agentName }: ShareLinkDialogProps) {
  const [open, setOpen] = useState(false);
  const [lastCreated, setLastCreated] = useState<ShareLink | null>(null);
  const { data: links, isLoading } = useShareLinks(agentId);

  const activeLinks = (links ?? []).filter((l) => l.is_active && !isExpired(l.expires_at));

  const handleCreated = useCallback((link: ShareLink) => {
    setLastCreated(link);
  }, []);

  return (
    <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) setLastCreated(null); }}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Share2 className="mr-1.5 h-3.5 w-3.5" />
          Share Demo
        </Button>
      </DialogTrigger>

      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Share2 className="h-4 w-4" />
            Share &ldquo;{agentName}&rdquo;
          </DialogTitle>
          <DialogDescription>
            Generate a link to share with clients so they can talk to this agent
            directly — no account needed.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5">
          {/* New link form */}
          <NewLinkForm agentId={agentId} onCreated={handleCreated} />

          {/* Newly created banner */}
          {lastCreated && <CreatedLinkBanner link={lastCreated} />}

          {/* Active links list */}
          {isLoading ? (
            <div className="flex justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : activeLinks.length > 0 ? (
            <>
              <Separator />
              <div className="space-y-2">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Active links
                </p>
                {activeLinks.map((link) => (
                  <LinkRow key={link.id} link={link} agentId={agentId} />
                ))}
              </div>
            </>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
