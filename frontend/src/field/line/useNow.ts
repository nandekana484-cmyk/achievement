// 今の時刻(ミリ秒)を一定の間隔で更新するフック。offsetMs(サーバー − タブレット)で時計のずれを補正する。
import { useEffect, useState } from "react";

export function useNow(intervalMs: number, offsetMs = 0): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(timer);
  }, [intervalMs]);
  return now + offsetMs;
}
