import { redirect } from 'next/navigation';

// The Projects section is the connected-organization drill-down at /connect:
// organization → repositories → commits → the code review and the seven agents for that
// commit. A project is still created implicitly the first time a repository is connected
// (lib/github-connect.ts), and the deep project views stay under /projects/[projectId].
export default function ProjectsPage() {
  redirect('/connect');
}
