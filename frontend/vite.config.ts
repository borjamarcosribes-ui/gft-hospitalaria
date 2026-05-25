import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const backendTarget = 'http://localhost:8000';

function buildProxyConfig() {
  return {
    target: backendTarget,
    changeOrigin: true,
  };
}

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/gft': buildProxyConfig(),
      '/imports': buildProxyConfig(),
      '/cima': buildProxyConfig(),
      '/bifimed': buildProxyConfig(),
      '/health': buildProxyConfig(),
      '/admin': {
        ...buildProxyConfig(),
        bypass(req) {
          const acceptHeader = req.headers.accept ?? '';
          if (acceptHeader.includes('text/html')) {
            return '/index.html';
          }
          return undefined;
        },
      },
    },
  },
});
