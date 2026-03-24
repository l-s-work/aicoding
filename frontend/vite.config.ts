import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

const isProd = process.env.NODE_ENV === 'production';
const parsedDevPort = Number(process.env.VITE_DEV_PORT ?? 5180);
const devPort = Number.isInteger(parsedDevPort) && parsedDevPort > 0 ? parsedDevPort : 5180;
// API 代理目标优先读取环境变量：
// 1) Docker Compose 中使用 http://backend:8000
// 2) 本机直接开发时回退到 http://127.0.0.1:8000
const apiTarget = process.env.VITE_API_URL ?? 'http://127.0.0.1:8000';

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
    host: '0.0.0.0',
    // 默认使用 5180，避免和 Vite 常见默认端口 5173 冲突；
    // 也可通过 VITE_DEV_PORT 指定固定端口
    port: devPort,
    strictPort: false,
    // 开发环境代理，将 /api 请求转发到 FastAPI 后端
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
        // 前端统一使用 /api 前缀，后端也统一挂在 /api 下，因此不做 rewrite
      },
      '/uploads': {
        // 商品图片静态资源代理（开发环境）
        target: apiTarget,
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
