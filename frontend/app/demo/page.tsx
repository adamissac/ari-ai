import { redirect } from 'next/navigation';
import { DEMO_HOME } from '@/lib/demo/access';

export default function DemoRedirect() {
  redirect(DEMO_HOME);
}
