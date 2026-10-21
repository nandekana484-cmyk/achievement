// 管理画面の文言(日本語だけ。管理画面は言語を切り替えない)。{name} は差し込み。詳細: docs/design/admin.md
import { format, type Params } from "../i18n/translate";

const text = {
  "title": "管理画面",
  "loading": "読み込み中…",
  "save": "保存",
  "cancel": "やめる",
  "edit": "編集",
  "add": "追加",
  "deactivate": "無効にする",
  "activate": "有効に戻す",
  "active": "有効",
  "inactive": "無効",
  "yes": "○",
  "no": "-",
  "saved": "保存しました",
  "network": "通信できませんでした",
  "error": "エラー",
  "server": "サーバーでエラーが起きました({status})",
  "lineOption": "{name}({code})",

  "login.title": "管理画面にログイン",
  "login.workerId": "作業者ID",
  "login.password": "パスワード",
  "login.submit": "ログイン",
  "login.expired": "ログインが切れました。もう一度ログインしてください",
  "login.backToField": "現場の画面に戻る",

  "menu.equipment": "設備",
  "menu.reasons": "理由",
  "menu.lines": "ライン",
  "menu.operators": "作業者",
  "menu.password": "パスワードの変更",
  "menu.logout": "ログアウト",
  "menu.user": "{name}({id})",

  "col.line": "ライン",
  "col.name": "名前",
  "col.nameVi": "ベトナム語の名前",
  "col.sort": "並び順",
  "col.state": "状態",
  "col.actions": "操作",
  "col.category": "区分",
  "col.requiresEquipment": "設備が必要",
  "col.requiresText": "記入が必要",
  "col.lineEvent": "付帯作業",
  "col.restart": "再開理由",
  "col.utilization": "稼働率に含める",
  "col.code": "記号",
  "col.autoNamed": "自動で付けた名前",
  "col.workerId": "作業者ID",
  "col.role": "役割",
  "col.source": "取り込み元",
  "col.password": "パスワード",

  "category.loss": "ロス",
  "category.non_loss": "ロス以外",
  "role.admin": "管理者",
  "role.operator": "作業者",
  "source.legacy": "既存アプリ",
  "source.local": "開発用",
  "password.set": "設定済み",
  "password.unset": "未設定",

  "equipment.title": "設備",
  "equipment.addTitle": "設備を追加",
  "equipment.note": "無効にした設備は、現場の画面で選べなくなります。過去の記録の表示は変わりません。",
  "reasons.title": "理由(付帯作業の種類と、生産の再開理由)",
  "reasons.addTitle": "理由を追加",
  "reasons.note": "無効にした理由は、現場の画面で選べなくなります。過去の記録の表示は変わりません。",
  "lines.title": "ライン",
  "lines.note": "ラインは計画の同期で自動で登録されます。名前を変えると、自動で付けた名前の扱い(現場の画面の言語に合わせた表示)は外れます。",
  "operators.title": "作業者",
  "operators.note": "作業者は既存アプリから読み込みます。ここでは変えられません。管理画面のパスワードは、担当者PCで開発用コマンド(admin set-password)で設定します。",
  "operators.addTitle": "開発用の作業者を追加(既存アプリを読まない環境だけ)",

  "password.title": "パスワードの変更",
  "password.current": "今のパスワード",
  "password.new": "新しいパスワード(8文字以上)",
  "password.confirm": "新しいパスワード(確認)",
  "password.mismatch": "新しいパスワードが確認と違います",
  "password.changed": "パスワードを変えました",
};

export type AdminKey = keyof typeof text;

/** 管理画面の文言。 */
export function at(key: AdminKey, params?: Params): string {
  return format(text[key], params);
}
