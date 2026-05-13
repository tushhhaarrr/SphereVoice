/**
 * Invite acceptance page — /invite/[token]
 *
 * Public page: no auth required. The invited user enters their
 * display name and a new password, which creates their account
 * and signs them in immediately.
 */

"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { signIn } from "next-auth/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, ShieldCheck } from "lucide-react";

/**
 * Safely constructs API URLs to prevent /api/v1/api/v1 duplication.
 */
const getApiUrl = (endpoint: string) => {
    const base = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
        .replace(/\/api\/v1\/?$/, "")
        .replace(/\/+$/, "");
    const cleanEndpoint = endpoint.replace(/^\/+/, "");
    return `${base}/api/v1/${cleanEndpoint}`;
};

interface InviteInfo {
    email: string;
    name: string | null;
    role: string;
    expires_at: string;
}

type PageState = "loading" | "valid" | "invalid" | "success";

export default function AcceptInvitePage() {
    const params = useParams<{ token: string }>();
    const router = useRouter();

    const [pageState, setPageState] = useState<PageState>("loading");
    const [invite, setInvite] = useState<InviteInfo | null>(null);
    const [errorMessage, setErrorMessage] = useState("");

    const [name, setName] = useState("");
    const [password, setPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [submitting, setSubmitting] = useState(false);

    /* ── Load invite info ─────────────────────────────────── */
    useEffect(() => {
        fetch(getApiUrl(`auth/invite/${params.token}`))
            .then(async (res) => {
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    setErrorMessage(
                        data.detail?.error?.message ||
                        "This invitation is invalid or has expired."
                    );
                    setPageState("invalid");
                    return;
                }
                const data: InviteInfo = await res.json();
                setInvite(data);
                setName(data.name ?? "");
                setPageState("valid");
            })
            .catch(() => {
                setErrorMessage("Could not reach the server. Please try again later.");
                setPageState("invalid");
            });
    }, [params.token]);

    /* ── Accept handler ───────────────────────────────────── */
    const handleAccept = async (e: React.FormEvent) => {
        e.preventDefault();
        if (password !== confirmPassword) {
            setErrorMessage("Passwords do not match.");
            return;
        }
        setErrorMessage("");
        setSubmitting(true);

        try {
            const res = await fetch(
                getApiUrl(`auth/invite/${params.token}/accept`),
                {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ name, password }),
                }
            );

            if (!res.ok) {
                const data = await res.json().catch(() => ({}));
                setErrorMessage(
                    data.detail?.error?.message || "Failed to create account. Please try again."
                );
                setSubmitting(false);
                return;
            }

            // Sign in via NextAuth so the session is established
            const result = await signIn("credentials", {
                email: invite!.email,
                password,
                redirect: false,
            });

            if (result?.ok) {
                setPageState("success");
                setTimeout(() => router.replace("/agents"), 1500);
            } else {
                // Account created but auto-login failed — send to login page
                router.replace("/login");
            }
        } catch {
            setErrorMessage("Something went wrong. Please try again.");
            setSubmitting(false);
        }
    };

    /* ── Render ───────────────────────────────────────────── */
    return (
        <div className="flex min-h-screen items-center justify-center bg-background px-4">
            <div className="absolute inset-0 z-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-primary/10 via-background to-background" />
            <div className="z-10 w-full max-w-sm space-y-6 animate-in fade-in zoom-in-95 duration-500">
                {/* Header */}
                <div className="space-y-1 text-center">
                    <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary ring-1 ring-primary/25">
                        <ShieldCheck className="h-6 w-6" />
                    </div>
                    <h1 className="text-3xl font-bold tracking-tight">SphereVoice</h1>
                    <p className="text-sm text-muted-foreground">
                        Enterprise Voice AI Platform
                    </p>
                </div>

                {/* Loading */}
                {pageState === "loading" && (
                    <div className="flex flex-col items-center justify-center space-y-3 rounded-xl border bg-card/50 p-8 shadow-sm backdrop-blur-sm">
                        <Loader2 className="h-6 w-6 animate-spin text-primary" />
                        <p className="text-sm text-muted-foreground">Verifying invitation...</p>
                    </div>
                )}

                {/* Invalid / expired */}
                {pageState === "invalid" && (
                    <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-center space-y-3">
                        <p className="font-semibold text-destructive">Invitation unavailable</p>
                        <p className="text-sm text-muted-foreground">{errorMessage}</p>
                        <Button variant="outline" className="w-full" onClick={() => router.replace("/login")}>
                            Go to login
                        </Button>
                    </div>
                )}

                {/* Success */}
                {pageState === "success" && (
                    <div className="rounded-lg border border-green-500/30 bg-green-500/5 p-4 text-center space-y-2">
                        <p className="font-semibold text-green-700 dark:text-green-400">
                            Account created!
                        </p>
                        <p className="text-sm text-muted-foreground">
                            Signing you in…
                        </p>
                    </div>
                )}

                {/* Form */}
                {pageState === "valid" && invite && (
                    <form onSubmit={handleAccept} className="space-y-4 rounded-xl border bg-card p-6 shadow-sm backdrop-blur-sm">
                        <div className="rounded-lg bg-muted/50 p-4 text-sm space-y-1">
                            <p className="font-medium">You're invited!</p>
                            <p className="text-muted-foreground">
                                <span className="font-mono">{invite.email}</span> —{" "}
                                <span className="capitalize">
                                    {invite.role.replace("_", " ")}
                                </span>{" "}
                                role
                            </p>
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="acc-name">Your name</Label>
                            <Input
                                id="acc-name"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                placeholder="Full name"
                                required
                                autoComplete="name"
                            />
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="acc-password">Password</Label>
                            <Input
                                id="acc-password"
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                placeholder="At least 8 characters"
                                required
                                minLength={8}
                                autoComplete="new-password"
                            />
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="acc-confirm">Confirm password</Label>
                            <Input
                                id="acc-confirm"
                                type="password"
                                value={confirmPassword}
                                onChange={(e) => setConfirmPassword(e.target.value)}
                                placeholder="Repeat your password"
                                required
                                minLength={8}
                                autoComplete="new-password"
                            />
                        </div>

                        {errorMessage && (
                            <p className="text-sm text-destructive">{errorMessage}</p>
                        )}

                        <Button
                            type="submit"
                            disabled={submitting || !name.trim() || !password || !confirmPassword}
                            className="w-full"
                        >
                            {submitting ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Creating account…
                                </>
                            ) : (
                                "Create account & sign in"
                            )}
                        </Button>
                    </form>
                )}
            </div>
        </div>
    );
}
