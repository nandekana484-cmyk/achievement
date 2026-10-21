// ライン画面用の取得(board)を5秒ごとに読み直すフック。画面が非表示のあいだは止める。
// あわせて、サーバーの時計とタブレットの時計の差を測る(今の時刻の線の補正に使う)。
import { useCallback, useEffect, useRef, useState } from "react";
import { useI18n } from "../../i18n/I18nProvider";
import { api, type Board } from "../../shared/api";
import { clockOffset } from "./timeScale";

export const BOARD_INTERVAL_MS = 5000;

type BoardState = { board: Board | null; error: string | null; offsetMs: number; reload: () => void };

export function useBoard(lineCode: string): BoardState {
  const [board, setBoard] = useState<Board | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [offsetMs, setOffsetMs] = useState(0);
  const seq = useRef(0);
  const { t } = useI18n();
  const tRef = useRef(t); // 言語を切り替えても読み直しの間隔を変えない(失敗の文はその時点の言語)
  tRef.current = t;

  const reload = useCallback(() => {
    const mine = ++seq.current; // 古い応答があとから届いても、新しい応答で上書きされないようにする
    const sent = Date.now();
    api
      .GET("/api/lines/{line_code}/board", { params: { path: { line_code: lineCode } } })
      .then(({ data, error: e }) => {
        if (mine !== seq.current) return;
        if (data) {
          setBoard(data);
          setOffsetMs(clockOffset(data.server_time, sent, Date.now()));
          setError(null);
        } else {
          setError(typeof e?.detail === "string" ? e.detail : tRef.current("error.boardLoad"));
        }
      })
      .catch(() => mine === seq.current && setError(tRef.current("error.connection")));
  }, [lineCode]);

  useEffect(() => {
    let timer: number | undefined;
    const start = () => {
      if (timer === undefined) timer = window.setInterval(reload, BOARD_INTERVAL_MS);
    };
    const stop = () => {
      window.clearInterval(timer);
      timer = undefined;
    };
    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        reload();
        start();
      } else {
        stop();
      }
    };
    reload();
    if (document.visibilityState === "visible") start();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      stop();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [reload]);

  return { board, error, offsetMs, reload };
}
