import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
    reporters: ['default', 'junit'],
    outputFile: {
      junit: '../docs/test-reports/frontend-junit.xml',
    },
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary'],
      reportsDirectory: '../docs/test-reports/frontend-coverage',
    },
  },
});
