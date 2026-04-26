import path from "node:path";
import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs";

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  turbopack: {
    root: path.join(__dirname, ".."),
  },
  // Proxy API requests to FastAPI in development
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:2998"}/api/v1/:path*`,
      },
    ];
  },
};

export default withSentryConfig(nextConfig, {
  // Use the Sentry org and project for source map uploads
  org: "Sphereai",
  project: "SphereVoice-frontend",

  // Only print logs for uploading source maps in CI
  silent: !process.env.CI,

  // Upload a larger set of source maps for prettier stack traces (increases build time)
  widenClientFileUpload: true,

  // Automatically tree-shake Sentry logger statements to reduce bundle size
  disableLogger: true,
});
