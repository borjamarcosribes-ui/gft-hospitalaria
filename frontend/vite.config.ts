import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/gft': 'http://localhost:8000',
      '/imports': 'http://localhost:8000',
      '/cima': 'http://localhost:8000',
      '/bifimed': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/admin/health': 'http://localhost:8000',
      '/admin/gft/medicamentos': 'http://localhost:8000',
    },
  },
});
