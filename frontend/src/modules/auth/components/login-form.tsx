"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Eye, EyeOff, Loader2, KeyRound, Sparkles } from "lucide-react";
import { motion } from "framer-motion";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { credentialsSignIn } from "@/app/actions/auth";

const loginSchema = z.object({
    email: z.string().email("Enter a valid email address"),
    password: z.string().min(1, "Password is required"),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export function LoginForm() {
    const router = useRouter();
    const [error, setError] = useState<string | null>(null);
    const [showPassword, setShowPassword] = useState(false);
    const [isPending, startTransition] = useTransition();

    const {
        register,
        handleSubmit,
        formState: { errors, isSubmitting },
    } = useForm<LoginFormValues>({
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        resolver: zodResolver(loginSchema as any),
        defaultValues: { email: "", password: "" },
    });

    async function onSubmit(data: LoginFormValues) {
        setError(null);

        const formData = new FormData();
        formData.set("email", data.email);
        formData.set("password", data.password);

        startTransition(async () => {
            try {
                const result = await credentialsSignIn({ error: null }, formData);
                if (result?.error) {
                    setError(result.error);
                } else {
                    router.push("/agents");
                    router.refresh();
                }
            } catch (err) {
                const msg = (err as Error)?.message ?? "";
                if (!msg.includes("NEXT_REDIRECT") && !msg.includes("NEXT_NOT_FOUND")) {
                    setError("Invalid email or password");
                }
            }
        });
    }

    const isLoading = isSubmitting || isPending;

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            className="w-full max-w-md"
        >
            <div className="relative z-10 flex flex-col items-center mb-8">
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 shadow-xl shadow-indigo-500/20 mb-6">
                    <Sparkles className="h-8 w-8 text-white" />
                </div>
                <h1 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white">Welcome back</h1>
                <p className="text-sm text-slate-500 mt-2 dark:text-slate-400">
                    Sign in to orchestrate your voice agents
                </p>
            </div>

            <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 rounded-2xl border border-white/20 bg-white/60 p-8 shadow-2xl backdrop-blur-xl dark:border-slate-800/50 dark:bg-slate-900/60 relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-br from-white/40 to-white/0 dark:from-white/5 dark:to-transparent pointer-events-none" />
                
                <div className="space-y-2 relative z-10">
                    <Label htmlFor="email" className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Email Address</Label>
                    <Input
                        id="email"
                        type="email"
                        placeholder="you@company.com"
                        autoComplete="email"
                        className="h-12 bg-white/50 dark:bg-slate-950/50 border-slate-200 dark:border-slate-800 transition-all focus:ring-2 focus:ring-indigo-500/50"
                        aria-invalid={!!errors.email}
                        {...register("email")}
                    />
                    {errors.email && (
                        <motion.p initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} className="text-xs text-red-500">{errors.email.message}</motion.p>
                    )}
                </div>

                <div className="space-y-2 relative z-10">
                    <div className="flex items-center justify-between">
                        <Label htmlFor="password" className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Password</Label>
                        <a href="#" className="text-xs font-medium text-indigo-600 hover:text-indigo-500 dark:text-indigo-400 transition-colors">Forgot password?</a>
                    </div>
                    <div className="relative">
                        <KeyRound className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" />
                        <Input
                            id="password"
                            type={showPassword ? "text" : "password"}
                            placeholder="••••••••"
                            autoComplete="current-password"
                            className="h-12 pl-10 bg-white/50 dark:bg-slate-950/50 border-slate-200 dark:border-slate-800 transition-all focus:ring-2 focus:ring-indigo-500/50"
                            aria-invalid={!!errors.password}
                            {...register("password")}
                        />
                        <button
                            type="button"
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors"
                            onClick={() => setShowPassword((v) => !v)}
                            tabIndex={-1}
                        >
                            {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                        </button>
                    </div>
                    {errors.password && (
                        <motion.p initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} className="text-xs text-red-500">{errors.password.message}</motion.p>
                    )}
                </div>

                {error && (
                    <motion.div 
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="rounded-lg bg-red-50 p-3 text-sm text-red-600 border border-red-100 dark:bg-red-500/10 dark:border-red-500/20 dark:text-red-400 relative z-10"
                    >
                        {error}
                    </motion.div>
                )}

                <Button 
                    type="submit" 
                    className="w-full h-12 mt-2 bg-slate-900 hover:bg-slate-800 text-white dark:bg-indigo-600 dark:hover:bg-indigo-700 transition-all relative z-10 shadow-lg shadow-slate-900/10 dark:shadow-indigo-900/20" 
                    disabled={isLoading}
                >
                    {isLoading ? (
                        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center">
                            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                            Establishing alignment...
                        </motion.div>
                    ) : (
                        "Sign In"
                    )}
                </Button>
            </form>
            
            <p className="mt-8 text-center text-sm text-slate-500 dark:text-slate-400">
                Don't have an account? <a href="#" className="font-semibold text-indigo-600 hover:underline dark:text-indigo-400">Contact Sales</a>
            </p>
        </motion.div>
    );
}