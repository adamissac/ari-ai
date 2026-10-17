'use client';

import type { ReactNode } from 'react';
import { ProjectShell } from '@/components/project';

export default function ProjectLayout({ children }: { children: ReactNode }) {
  return <ProjectShell>{children}</ProjectShell>;
}
