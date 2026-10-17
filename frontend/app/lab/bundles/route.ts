import { listProtocols } from '@/lib/lab-bundle';

export const dynamic = 'force-dynamic';

export async function GET() {
  return Response.json({ protocols: await listProtocols() });
}
