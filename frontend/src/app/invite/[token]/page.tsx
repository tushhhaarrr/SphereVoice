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

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:2998";

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
        fetch(`${API_BASE}/api/v1/auth/invite/${params.token}`)
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
                `${API_BASE}/api/v1/auth/invite/${params.token}/accept`,
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
            <div className="w-full max-w-sm space-y-6">
                {/* Header */}
                <div className="space-y-1 text-center">
                    <h1 className="text-3xl font-bold tracking-tight">SphereVoice</h1>
                    <p className="text-sm text-muted-foreground">
                        Voice AI Agent Platform by Gorillaa AI
                    </p>
                </div>

                {/* Loading */}
                {pageState === "loading" && (
                    <div className="space-y-3">
                        {[1, 2, 3].map((i) => (
                            <div key={i} className="h-10 animate-pulse rounded-md bg-muted" />
                        ))}
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
                    <form onSubmit={handleAccept} className="space-y-4">
                        <div className="rounded-lg border bg-card p-4 text-sm space-y-1">
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
                            {submitting ? "Creating account…" : "Create account & sign in"}
                        </Button>
                    </form>
                )}
            </div>
        </div>
    );
}
