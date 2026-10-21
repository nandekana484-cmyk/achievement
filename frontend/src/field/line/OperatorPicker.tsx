// 今の担当者を選ぶ画面。作業者IDを入れて呼び出し、IDと名前を確かめてから決める。名前の一覧から選ぶ方法は補助。
// 入力欄はバーコードリーダー(文字の入力 + Enter)でも動く。
import { useState } from "react";
import { useI18n } from "../../i18n/I18nProvider";
import { api, type Operator } from "../../shared/api";
import { Dialog } from "../../shared/Dialog";
import { operatorLabel, sortOperators } from "./operatorLabel";

type Props = {
  operators: Operator[];
  currentId: number | null;
  message?: string; // 担当者が未設定のままボタンを押したときの案内など
  onPick: (id: number) => void;
  onCancel: () => void;
};

export function OperatorPicker({ operators, currentId, message, onPick, onCancel }: Props) {
  const { t } = useI18n();
  const [workerId, setWorkerId] = useState("");
  const [found, setFound] = useState<Operator | null>(null);
  const [error, setError] = useState<string | null>(null);

  const lookup = async () => {
    setFound(null);
    setError(null);
    if (!workerId.trim()) return;
    try {
      const { data, error: e } = await api.GET("/api/operators/lookup", { params: { query: { worker_id: workerId } } });
      if (data) setFound(data);
      else setError(typeof e?.detail === "string" ? e.detail : t("operator.notFound"));
    } catch {
      setError(t("error.connection"));
    }
  };

  return (
    <Dialog
      title={t("operator.title")}
      wide
      onCancel={onCancel}
      actions={found && (
        <button type="button" className="btn btn-primary" onClick={() => onPick(found.id)}>{t("operator.confirm")}</button>
      )}
    >
      {message && <p className="dialog-error" role="status">{message}</p>}
      <label className="field-label" htmlFor="worker-id">{t("operator.workerId")}</label>
      <div className="worker-id-row">
        <input
          id="worker-id"
          className="text-input worker-id-input"
          type="text"
          inputMode="text"
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="characters"
          spellCheck={false}
          maxLength={64}
          autoFocus
          placeholder={t("operator.workerIdPlaceholder")}
          value={workerId}
          onChange={(e) => {
            setWorkerId(e.target.value);
            setFound(null);
            setError(null);
          }}
          onKeyDown={(e) => e.key === "Enter" && void lookup()}
        />
        <button type="button" className="btn" onClick={() => void lookup()} disabled={!workerId.trim()}>{t("operator.lookup")}</button>
      </div>
      {error && <p className="dialog-error" role="alert"><span className="notice-kind">{t("notice.error")}</span> {error}</p>}
      {found && (
        <div className="worker-found" role="status" aria-label={t("operator.foundAria")}>
          <span className="worker-found-label">{t("operator.foundQuestion")}</span>
          <span className="worker-found-id">{t("operator.foundId", { id: found.worker_id ?? "" })}</span>
          <span className="worker-found-name">{found.name}</span>
          {found.id === currentId && <span className="choice-note">{t("operator.current")}</span>}
        </div>
      )}

      <p className="picker-sub">{t("operator.byName")}</p>
      <div className="choice-grid">
        {sortOperators(operators).map((o) => (
          <button key={o.id} type="button" className={`btn choice${o.id === currentId ? " choice-selected" : ""}`} onClick={() => onPick(o.id)}>
            {operatorLabel(o.name, o.worker_id, t)}
            {o.id === currentId && <span className="choice-note">{t("operator.current")}</span>}
          </button>
        ))}
      </div>
      {operators.length === 0 && <p>{t("operator.none")}</p>}
    </Dialog>
  );
}
