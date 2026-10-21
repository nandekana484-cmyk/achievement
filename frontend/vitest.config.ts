import { defineConfig } from "vitest/config";

// 画面から切り離した処理(src/**/*.test.ts)と、APIの型の食い違いの検出(scripts/*.test.ts)のテスト。
// 画面の操作の確認は Playwright(e2e/)で行う。
export default defineConfig({
  test: {
    include: ["src/**/*.test.ts", "scripts/**/*.test.ts"],
    environment: "node",
  },
});
