import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 開発中は /api をバックエンド(uvicorn, 8000番)へ転送する。
// 本番はビルドした dist をFastAPIが配信するので、この設定は使われない。
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
});
