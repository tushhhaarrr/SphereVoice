import * as Sentry from "@sentry/nextjs";

if (process.env.NODE_ENV === "production") {
    Sentry.init({
        dsn: "https://f55d437fc86500fdc58e43d6aeba2be9@o4511054255751168.ingest.us.sentry.io/4511054482374656",
        tracesSampleRate: parseFloat(process.env.SENTRY_TRACES_SAMPLE_RATE || "0.1"),
        environment: process.env.SENTRY_ENVIRONMENT || "production",
    });
}
