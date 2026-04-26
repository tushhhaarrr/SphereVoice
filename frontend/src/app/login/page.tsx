/**
 * Login page — /login
 *
 * Full-screen login form for email/password auth.
 * Uses Auth.js CredentialsProvider to call FastAPI backend.
 */

import { LoginForm } from "@/modules/auth";

export const metadata = {
    title: "Sign In — SphereVoice",
};

export default function LoginPage() {
    return (
        <div className="flex min-h-screen items-center justify-center bg-background px-4">
            <div className="w-full max-w-sm space-y-6">
                <div className="space-y-2 text-center">
                    <h1 className="text-3xl font-bold tracking-tight">SphereVoice</h1>
                    <p className="text-sm text-muted-foreground">
                        Voice AI Agent Platform by Sphere AI
                    </p>
                </div>
                <LoginForm />
            </div>
        </div>
    );
}
