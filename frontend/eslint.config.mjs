import nextVitals from 'eslint-config-next/core-web-vitals';
import nextTs from 'eslint-config-next/typescript';

export default [
  ...nextVitals,
  ...nextTs,
  { ignores: ['.next/**', 'transport/**', 'node_modules/**', 'test-results/**', 'playwright-report/**', 'next-env.d.ts'] },
];
