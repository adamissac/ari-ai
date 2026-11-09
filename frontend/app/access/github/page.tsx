import type { Metadata } from 'next';
import { safeNext } from '@/lib/demo/access';
import { GitHubStep } from './github-step';

export const metadata: Metadata = { title: 'Connect GitHub', robots: { index: false, follow: false } };

export default async function DemoGitHubPage({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const { next } = await searchParams;
  return <GitHubStep next={safeNext(next)} />;
}
