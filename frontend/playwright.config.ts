import { defineConfig } from "@playwright/test";

// 画面の確認(npm run e2e)。確認用のデータを入れたDBでバックエンドを起動し、ビルドした画面を操作する。
// 実行の前に npm run build と、初回だけ npx playwright install chromium が必要。
const PORT = 8765;

export default defineConfig({
  testDir: "e2e",
  outputDir: "test-results/playwright",
  timeout: 60_000,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    viewport: { width: 1280, height: 800 }, // タブレットの横向き
    locale: "ja-JP",
    timezoneId: "Asia/Tokyo",
  },
  webServer: {
    command: `node e2e/serve.mjs ${PORT}`,
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
