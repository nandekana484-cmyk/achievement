// 画面の文言(ベトナム語)。ja.ts と同じキーをすべて持つ(抜けや余分なキーがあると型のエラー)。画面ごとのファイル(vi/*.ts)を集める。
// 訳はレビュー役が入れた(2026-10-21 初版、同日に用語を見直し)。現場の用語は、使いながら直す。{name} の差し込みは ja.ts と同じ名前を使う。
// 詳細: docs/design/i18n.md
import type { Messages } from "./ja";
import { common } from "./vi/common";
import { idslip } from "./vi/idslip";
import { line } from "./vi/line";
import { link } from "./vi/link";
import { planClose } from "./vi/planClose";
import { record } from "./vi/record";

export const vi: Messages = { ...common, ...line, ...link, ...record, ...idslip, ...planClose };
