// 画面の文言(日本語。基準)。キーは「画面や部品.項目」。{name} は差し込み。
// 画面ごとのファイル(ja/*.ts)を集める。vi.ts は同じキーをすべて持つ(抜けがあると型のエラー)。サーバーが返す理由の文と計画の内容は訳さない。
// 詳細: docs/design/i18n.md
import { common } from "./ja/common";
import { idslip } from "./ja/idslip";
import { line } from "./ja/line";
import { record } from "./ja/record";

export const ja = { ...common, ...line, ...record, ...idslip };

export type MessageKey = keyof typeof ja;
export type Messages = Record<MessageKey, string>;
