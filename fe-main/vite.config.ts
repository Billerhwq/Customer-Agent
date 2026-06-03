import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 开发时把 API 请求代理到后端 FastAPI（默认 8000 端口），避免跨域问题。
export default defineConfig({
  plugins: [react()],
  // 显式禁用 PostCSS 配置查找，避免误用上层目录（如 G:\postcss.config.js）的配置
  css: { postcss: {} },
  server: {
    port: 5181,
    strictPort: true,
    proxy: {
      "/chat": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
      "/lead": "http://127.0.0.1:8000",
    },
  },
});
