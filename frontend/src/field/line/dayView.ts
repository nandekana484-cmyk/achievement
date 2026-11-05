// 表示する稼働日(ライン画面の ?day=YYYY-MM-DD)の決まり。選べるのは今日の31日前から14日後まで。詳細: docs/design/line-screen.md
export const DAYS_BACK = 31;
export const DAYS_FORWARD = 14;

const DAY_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

/** URL の day を読む。日付の形でなければ null(今日を出す)。 */
export function parseDay(value: string | null): string | null {
  if (!value || !DAY_PATTERN.test(value)) return null;
  return Number.isNaN(Date.parse(`${value}T00:00:00Z`)) ? null : value;
}

export function addDays(day: string, days: number): string {
  const d = new Date(`${day}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

/** 選べる日の範囲(今日の稼働日が基準)。 */
export function dayBounds(today: string): { min: string; max: string } {
  return { min: addDays(today, -DAYS_BACK), max: addDays(today, DAYS_FORWARD) };
}

export function isSelectableDay(day: string, today: string): boolean {
  const { min, max } = dayBounds(today);
  return parseDay(day) !== null && day >= min && day <= max;
}

/** 今日以外の稼働日を見ている(表示のみ)。 */
export const isReadOnlyDay = (board: { date: string; today: string } | null | undefined): boolean => !!board && board.date !== board.today;
