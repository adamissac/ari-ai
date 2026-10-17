import path from 'node:path';
import type { NextConfig } from 'next';

// The browser talks only to this origin; app/api/v1/[...path] proxies to the FastAPI
// control plane at BACKEND_ORIGIN, read at request time (one build, any backend).
const config: NextConfig = {
  reactStrictMode: true,
  // gzip buffers proxied text/event-stream responses, so live assessment events would
  // arrive only when the stream closes. Leave compression to a fronting proxy.
  compress: false,
  poweredByHeader: false,
  // The transport package is a symlinked local workspace dependency.
  turbopack: { root: path.resolve(import.meta.dirname, '..') },
  outputFileTracingRoot: path.resolve(import.meta.dirname, '..'),
  async headers() {
    return [{
      source: '/:path*',
      headers: [
        { key: 'X-Content-Type-Options', value: 'nosniff' },
        { key: 'Referrer-Policy', value: 'same-origin' },
        { key: 'X-Frame-Options', value: 'DENY' },
      ],
    }];
  },
};
export default config;
