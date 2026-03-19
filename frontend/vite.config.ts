import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

const isProd = process.env.NODE_ENV === 'production';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // 使用 @ 作为 src 目录别名，避免层层相对路径
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    // 开发环境代理，将 /api 请求转发到 FastAPI 后端
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    target: 'es2015',
    // 开发开启 sourcemap 方便断点调试，生产关闭防止源码泄露
    sourcemap: !isProd,
    // 生产用 terser（压缩率更高），开发不压缩提升构建速度
    minify: isProd ? 'terser' : false,
    terserOptions: {
      compress: {
        drop_console: isProd, // 生产环境移除 console
        drop_debugger: isProd, // 生产环境移除 debugger
      },
    },
    // 生产环境压缓 CSS，开发不压缩
    cssMinify: isProd,
    // react + antd 合并到同一 chunk 体积约 550KB，调高阈值消除误报警告
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            // antd / @ant-design/x 均依赖 react，统一放入 vendor-ui
            if (id.includes('react') || id.includes('react-router') || id.includes('antd') || id.includes('@ant-design')) return 'vendor-ui';
            if (id.includes('zustand')) return 'vendor-state';
            if (id.includes('axios') || id.includes('styled-components')) return 'vendor-utils';
          }
        },
      },
    },
  },
});
