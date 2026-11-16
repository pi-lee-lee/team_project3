import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// 개발 서버(npm run dev)에서는 compose 로 띄운 web(nginx) 을 통해 API 를 호출한다.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8080',
      '/ws': { target: 'ws://localhost:8080', ws: true },
    },
  },
});
