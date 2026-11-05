import { defineConfig } from "@playwright/test";

// 画面の確認(npm run e2e)。確認用のデータを入れたDBでバックエンドを起動し、ビルドした画面を操作する。
// 実行の前に npm run build と、初回だけ npx playwright install chromium が必要。
const PORT = 8765;

export default defineConfig({
  testDir: "e2e",
  outputDir: "test-results/playwright",
  timeout: 60_000,
  expect: { timeout: 10_000 }, // 既定は 5 秒。ビルドの直後の最初の実行は、画面の読み込みが遅いことがある(AD-28 の直し。docs/STATUS.md の既知の課題)
  workers: 1,
  reporter: "list",
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    viewport: { width: 1280, height: 800 }, // タブレットの横向き
    locale: "ja-JP",
    timezoneId: "Asia/Tokyo",
    trace: "retain-on-failure", // 失敗したときだけ、トレースとスクリーンショットを test-results/playwright に残す(原因を調べるため)
    screenshot: "only-on-failure",
  },
  webServer: {
    command: `node e2e/serve.mjs ${PORT}`,
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
