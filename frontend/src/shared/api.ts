// APIクライアント。型は src/api/schema.ts(npm run gen:api で自動生成)から取る。手書きの fetch は使わない。
import createClient from "openapi-fetch";
import type { components, paths } from "../api/schema";

export const api = createClient<paths>({ baseUrl: "" });

type Schemas = components["schemas"];
export type Board = Schemas["BoardOut"];
export type BoardPlan = Schemas["BoardPlanOut"];
export type Plan = Schemas["PlanOut"];
export type RunEvent = Schemas["RunEventOut"];
export type LineEvent = Schemas["LineEventOut"];
export type Masters = Schemas["MastersOut"];
export type Reason = Schemas["ReasonOut"];
export type Equipment = Schemas["EquipmentOut"];
export type Operator = Schemas["OperatorOut"];
export type CurrentOperator = Schemas["CurrentOperatorOut"];
export type StepType = Schemas["StepType"];
