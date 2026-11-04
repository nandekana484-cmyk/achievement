// 識別票のバーコード。大きさは mm で決める(scale は、識別票全体を縮めて描くときの縮尺。縮めたあとの印刷の大きさが barMm になる)。
// Code 39 で表せない値は、バーコードを描かずに値の文字だけを出す(操作バーに警告を出す)。
import { useMemo } from "react";
import { barsPath, encodeCode39 } from "./code39";

type Props = { value: string; barMm: number; heightMm: number; scale?: number; label?: boolean };

export function Barcode({ value, barMm, heightMm, scale = 1, label = false }: Props) {
  const data = useMemo(() => encodeCode39(value), [value]);
  if (!data) return <span className="slip-bc-fallback">{value}</span>;
  return (
    <span className="slip-bc">
      <svg
        className="slip-bc-svg" data-modules={data.length} data-bar-mm={barMm} aria-label={value} role="img"
        width={`${(data.length * barMm) / scale}mm`} height={`${heightMm / scale}mm`}
        viewBox={`0 0 ${data.length} 1`} preserveAspectRatio="none" shapeRendering="crispEdges"
      >
        <path d={barsPath(data)} fill="#000" />
      </svg>
      {label && <span className="slip-bc-label">{value}</span>}
    </span>
  );
}
