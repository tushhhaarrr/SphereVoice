import * as Sentry from "@sentry/nextjs";
import posthog from 'posthog-js'

if (process.env.NODE_ENV === "production") {
    Sentry.init({
        dsn: "https://f55d437fc86500fdc58e43d6aeba2be9@o4511054255751168.ingest.us.sentry.io/4511054482374656",
        sendDefaultPii: true,
        tracesSampleRate: parseFloat(process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE || "0.1"),
        replaysSessionSampleRate: 0,
        replaysOnErrorSampleRate: 1.0,
        environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || "production",
        integrations: [Sentry.replayIntegration()],
        beforeSendTransaction(event) {
            const url = event.transaction || "";
            if (url.includes("/health") || url.includes("/ready") || url.startsWith("/_next/")) {
                return null;
            }
            return event;
        },
    });
}

posthog.init(process.env.NEXT_PUBLIC_POSTHOG_KEY!, {
    api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST,
    defaults: '2026-01-30'
})
