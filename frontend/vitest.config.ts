import { defineConfig } from "vitest/config";

// 画面から切り離した処理(src/**/*.test.ts)のテスト。画面の操作の確認は Playwright(e2e/)で行う。
export default defineConfig({
  test: {
    include: ["src/**/*.test.ts"],
    environment: "node",
  },
});
