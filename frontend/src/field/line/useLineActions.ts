// ライン画面のボタン操作(APIの呼び出し)。実績はキッティングNo.の単位。送り方は shared/useOperation.ts にまとめてある。
import { api, type BoardPlan, type LineEvent, type StepType } from "../../shared/api";
import type { Operation, RunOptions } from "../../shared/useOperation";
import { stepKey } from "./StepPanel";

const kittingPath = (p: BoardPlan) => ({ kitting_no: p.plan.kitting_no });

export function useLineActions(lineCode: string, op: Operation) {
  return {
    changeOperator: (operatorId: number) =>
      op.run("operator", { operatorId }, (request_id) =>
        api.PUT("/api/lines/{line_code}/operator", {
          params: { path: { line_code: lineCode } }, body: { request_id, operator_id: operatorId },
        })),

    startStep: (p: BoardPlan, step: StepType, restartReasonId: number | null = null, equipmentId: number | null = null) =>
      op.run(stepKey(p, step), { action: "start", restartReasonId, equipmentId }, (request_id) =>
        api.POST("/api/runs/{kitting_no}/steps/{step_type}/start", {
          params: { path: { ...kittingPath(p), step_type: step } },
          body: { request_id, restart_reason_id: restartReasonId, equipment_id: equipmentId },
        })),

    endStep: (p: BoardPlan, step: StepType, producedQty: number | null = null, options?: RunOptions) =>
      op.run(stepKey(p, step), { action: "end", producedQty }, (request_id) =>
        api.POST("/api/runs/{kitting_no}/steps/{step_type}/end", {
          params: { path: { ...kittingPath(p), step_type: step } },
          body: { request_id, produced_qty: producedQty },
        }), options),

    /** NG数。ロットと、NGが出た面を選んで入力する。 */
    setNg: (p: BoardPlan, lotNo: string, side: number, ngQty: number, options?: RunOptions) =>
      op.run(`ng:${p.plan.kitting_no}:${lotNo}:${side}`, { ngQty }, (request_id) =>
        api.PUT("/api/runs/{kitting_no}/ng-qty", {
          params: { path: kittingPath(p) }, body: { request_id, lot_no: lotNo, side, ng_qty: ngQty },
        }), options),

    addRemark: (p: BoardPlan, text: string) =>
      op.run(`remark:${p.plan.kitting_no}`, { text }, (request_id) =>
        api.POST("/api/runs/{kitting_no}/remarks", { params: { path: kittingPath(p) }, body: { request_id, text } })),

    startLineEvent: (reasonId: number, equipmentId: number | null, text: string | null) =>
      op.run(`lineEventStart:${reasonId}`, { equipmentId, text }, (request_id) =>
        api.POST("/api/lines/{line_code}/events/start", {
          params: { path: { line_code: lineCode } },
          body: { request_id, reason_id: reasonId, equipment_id: equipmentId, reason_text: text },
        })),

    endLineEvent: (e: LineEvent) =>
      op.run(`lineEventEnd:${e.id}`, {}, (request_id) =>
        api.POST("/api/lines/{line_code}/events/{event_id}/end", {
          params: { path: { line_code: lineCode, event_id: e.id } }, body: { request_id },
        })),
  };
}

export type LineActions = ReturnType<typeof useLineActions>;
