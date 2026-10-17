import type { Metadata } from 'next';
import { safeNext } from '@/lib/demo/access';
import { AccessForm } from './access-form';

export const metadata: Metadata = { title: 'Sign in', robots: { index: false, follow: false } };

export default async function AccessPage({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const { next } = await searchParams;
  return <AccessForm next={safeNext(next)} />;
}
