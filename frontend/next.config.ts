import path from 'node:path';
import type { NextConfig } from 'next';

// The browser talks only to this origin; /api/v1 is proxied to FastAPI so the
// backend's SameSite=Lax session cookie and CSRF flow work without CORS.
const backend = process.env.BACKEND_ORIGIN ?? 'http://127.0.0.1:8000';
if (!/^https?:\/\/[^/?#@]+$/.test(backend)) throw new Error('BACKEND_ORIGIN must be an http(s) origin without path or credentials');

const config: NextConfig = {
  reactStrictMode: true,
  // gzip buffers proxied text/event-stream responses, so live assessment events would
  // arrive only when the stream closes. Leave compression to a fronting proxy.
  compress: false,
  poweredByHeader: false,
  // The transport package is a symlinked local workspace dependency.
  turbopack: { root: path.resolve(import.meta.dirname, '..') },
  outputFileTracingRoot: path.resolve(import.meta.dirname, '..'),
  async rewrites() {
    return [{ source: '/api/v1/:path*', destination: `${backend}/api/v1/:path*` }];
  },
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
