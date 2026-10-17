import { proxy } from '@/lib/backend-proxy';

// Same-origin proxy to the FastAPI control plane, configured at runtime.
export const dynamic = 'force-dynamic';
export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
