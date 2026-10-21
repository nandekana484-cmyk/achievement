// ライン画面用の取得(board)を5秒ごとに読み直すフック。画面が非表示のあいだは止める。
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Board } from "../../shared/api";

export const BOARD_INTERVAL_MS = 5000;

export function useBoard(lineCode: string): { board: Board | null; error: string | null; reload: () => void } {
  const [board, setBoard] = useState<Board | null>(null);
  const [error, setError] = useState<string | null>(null);
  const seq = useRef(0);

  const reload = useCallback(() => {
    const mine = ++seq.current; // 古い応答があとから届いても、新しい応答で上書きされないようにする
    api
      .GET("/api/lines/{line_code}/board", { params: { path: { line_code: lineCode } } })
      .then(({ data, error: e }) => {
        if (mine !== seq.current) return;
        if (data) {
          setBoard(data);
          setError(null);
        } else {
          setError(typeof e?.detail === "string" ? e.detail : "ラインの情報を読めませんでした");
        }
      })
      .catch(() => mine === seq.current && setError("通信できませんでした。電波の状態を確かめてください"));
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

  return { board, error, reload };
}
