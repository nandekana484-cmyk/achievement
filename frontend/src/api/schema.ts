// このファイルは自動生成です。手で編集しないこと(npm run gen:api で作り直す)。
// 元: バックエンドの OpenAPI(app.openapi_export)、生成: openapi-typescript

export interface paths {
    "/api/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["health_api_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/lines/{line_code}/plans": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Line Plans
         * @description その日に計画開始〜終了が重なる有効な計画を、計画開始の順で返す。
         */
        get: operations["list_line_plans_api_lines__line_code__plans_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sync/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Sync Status
         * @description 直近の計画の同期の結果と、解決していない警告の件数。
         */
        get: operations["sync_status_api_sync_status_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/runs/{kitting_no}/{lot_no}/steps/{step_type}/start": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Start Step
         * @description 工程を開始する。
         */
        post: operations["start_step_api_runs__kitting_no___lot_no__steps__step_type__start_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/runs/{kitting_no}/{lot_no}/steps/{step_type}/end": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * End Step
         * @description 工程を終了する。片付けの終了では完了の記録も作る。
         */
        post: operations["end_step_api_runs__kitting_no___lot_no__steps__step_type__end_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/runs/{kitting_no}/{lot_no}/ng-qty": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Set Ng Qty
         * @description NG数を入力する(行を追加し、最新の値を有効とする)。
         */
        put: operations["set_ng_qty_api_runs__kitting_no___lot_no__ng_qty_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/runs/{kitting_no}/{lot_no}/remarks": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Add Remark
         * @description 備考を追加する。
         */
        post: operations["add_remark_api_runs__kitting_no___lot_no__remarks_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/lines/{line_code}/operator": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Operator
         * @description ラインの今の担当者(未設定なら null)。
         */
        get: operations["get_operator_api_lines__line_code__operator_get"];
        /**
         * Change Operator
         * @description ラインの今の担当者を交代する。
         */
        put: operations["change_operator_api_lines__line_code__operator_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/lines/{line_code}/events/start": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Start Line Event
         * @description 付帯作業を開始する。
         */
        post: operations["start_line_event_api_lines__line_code__events_start_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/lines/{line_code}/events/{event_id}/end": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * End Line Event
         * @description 付帯作業を終了する。
         */
        post: operations["end_line_event_api_lines__line_code__events__event_id__end_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/lines/{line_code}/board": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Board
         * @description ライン画面用: その日の計画ごとの工程の記録・生産数・NG数・完了・進捗率と、付帯作業、今の担当者。
         */
        get: operations["get_board_api_lines__line_code__board_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/masters": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Masters
         * @description 有効なマスタ(ライン・作業者・設備・理由)を sort_order 順に返す。
         */
        get: operations["get_masters_api_masters_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** BoardOut */
        BoardOut: {
            /** Line Code */
            line_code: string;
            /**
             * Date
             * Format: date
             */
            date: string;
            current_operator: components["schemas"]["CurrentOperatorOut"] | null;
            /** Plans */
            plans: components["schemas"]["BoardPlanOut"][];
            /** Line Events */
            line_events: components["schemas"]["LineEventOut"][];
            /** Line Progress */
            line_progress: number | null;
            /** Utilization */
            utilization: number | null;
        };
        /** BoardPlanOut */
        BoardPlanOut: {
            plan: components["schemas"]["PlanOut"];
            /** Events */
            events: components["schemas"]["RunEventOut"][];
            /** Produced Qty */
            produced_qty: number;
            /** Ng Qty */
            ng_qty: number | null;
            /** Completed */
            completed: boolean;
            completion: components["schemas"]["RunCompletionOut"] | null;
            /** Progress */
            progress: number | null;
        };
        /** ChangeOperatorIn */
        ChangeOperatorIn: {
            /**
             * Request Id
             * @description 操作ごとに一意のID。再送には同じIDを使う
             */
            request_id: string;
            /** Operator Id */
            operator_id: number;
        };
        /** CurrentOperatorOut */
        CurrentOperatorOut: {
            /** Line Code */
            line_code: string;
            /** Operator Id */
            operator_id: number;
            /** Operator Name */
            operator_name: string;
            /**
             * Start At
             * Format: date-time
             */
            start_at: string;
        };
        /** EquipmentOut */
        EquipmentOut: {
            /** Id */
            id: number;
            /** Line Code */
            line_code: string;
            /** Name */
            name: string;
            /** Sort Order */
            sort_order: number;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** LineEventEndIn */
        LineEventEndIn: {
            /**
             * Request Id
             * @description 操作ごとに一意のID。再送には同じIDを使う
             */
            request_id: string;
            /** Operator Id */
            operator_id?: number | null;
        };
        /** LineEventOut */
        LineEventOut: {
            /** Id */
            id: number;
            /** Line Code */
            line_code: string;
            /** Reason Id */
            reason_id: number;
            /** Reason Name */
            reason_name: string;
            /** Equipment Id */
            equipment_id: number | null;
            /** Equipment Name */
            equipment_name: string | null;
            /** Reason Text */
            reason_text: string | null;
            /**
             * Start At
             * Format: date-time
             */
            start_at: string;
            /** End At */
            end_at: string | null;
            /** Started By */
            started_by: number;
            /** Started By Name */
            started_by_name: string;
            /** Ended By */
            ended_by: number | null;
            /** Ended By Name */
            ended_by_name: string | null;
        };
        /** LineEventStartIn */
        LineEventStartIn: {
            /**
             * Request Id
             * @description 操作ごとに一意のID。再送には同じIDを使う
             */
            request_id: string;
            /** Reason Id */
            reason_id: number;
            /** Equipment Id */
            equipment_id?: number | null;
            /** Reason Text */
            reason_text?: string | null;
            /** Operator Id */
            operator_id?: number | null;
        };
        /** LineOut */
        LineOut: {
            /** Line Code */
            line_code: string;
            /** Name */
            name: string;
            /** Sort Order */
            sort_order: number;
        };
        /** MastersOut */
        MastersOut: {
            /** Lines */
            lines: components["schemas"]["LineOut"][];
            /** Operators */
            operators: components["schemas"]["OperatorOut"][];
            /** Equipment */
            equipment: components["schemas"]["EquipmentOut"][];
            /** Reasons */
            reasons: components["schemas"]["ReasonOut"][];
        };
        /** NgQtyIn */
        NgQtyIn: {
            /**
             * Request Id
             * @description 操作ごとに一意のID。再送には同じIDを使う
             */
            request_id: string;
            /** Ng Qty */
            ng_qty: number;
            /** Operator Id */
            operator_id?: number | null;
        };
        /** OperatorOut */
        OperatorOut: {
            /** Id */
            id: number;
            /** Name */
            name: string;
            /** Sort Order */
            sort_order: number;
        };
        /** PlanOut */
        PlanOut: {
            /** Kitting No */
            kitting_no: string;
            /** Lot No */
            lot_no: string;
            /** File No */
            file_no: string;
            /** Line Code */
            line_code: string;
            /** Product Name */
            product_name: string;
            /** Run No */
            run_no: number;
            /** Planned Qty */
            planned_qty: number;
            /** Cumulative Qty */
            cumulative_qty: number | null;
            /** Order Qty */
            order_qty: number | null;
            /**
             * Planned Start
             * Format: date-time
             */
            planned_start: string;
            /**
             * Planned End
             * Format: date-time
             */
            planned_end: string;
            /** Deadline */
            deadline: string | null;
            /**
             * Issue Date
             * Format: date
             */
            issue_date: string;
            /** Issue Seq */
            issue_seq: number;
            /** Legacy Status */
            legacy_status: string | null;
            /** Status */
            status: string;
            /** Takt Sec */
            takt_sec: number | null;
            /** Source Db */
            source_db: string | null;
        };
        /** ReasonOut */
        ReasonOut: {
            /** Id */
            id: number;
            /** Name */
            name: string;
            /** Category */
            category: string;
            /** Counts In Utilization */
            counts_in_utilization: boolean;
            /** Requires Equipment */
            requires_equipment: boolean;
            /** Requires Text */
            requires_text: boolean;
            /** Usable As Line Event */
            usable_as_line_event: boolean;
            /** Usable As Restart */
            usable_as_restart: boolean;
            /** Sort Order */
            sort_order: number;
        };
        /** RemarkIn */
        RemarkIn: {
            /**
             * Request Id
             * @description 操作ごとに一意のID。再送には同じIDを使う
             */
            request_id: string;
            /** Text */
            text: string;
            /** Operator Id */
            operator_id?: number | null;
        };
        /** RunCompletionOut */
        RunCompletionOut: {
            /** Id */
            id: number;
            /** Kitting No */
            kitting_no: string;
            /** Lot No */
            lot_no: string;
            /**
             * Completed At
             * Format: date-time
             */
            completed_at: string;
            /** Produced Qty */
            produced_qty: number;
            /** Ng Qty */
            ng_qty: number | null;
            /** Plan Qty Snapshot */
            plan_qty_snapshot: number;
            /** Takt Sec Snapshot */
            takt_sec_snapshot: number | null;
            /** Utilization */
            utilization: number | null;
        };
        /** RunEventOut */
        RunEventOut: {
            /** Id */
            id: number;
            /** Kitting No */
            kitting_no: string;
            /** Lot No */
            lot_no: string;
            /** Step Type */
            step_type: string;
            /** Seq */
            seq: number;
            /**
             * Start At
             * Format: date-time
             */
            start_at: string;
            /** End At */
            end_at: string | null;
            /** Started By */
            started_by: number;
            /** Started By Name */
            started_by_name: string;
            /** Ended By */
            ended_by: number | null;
            /** Ended By Name */
            ended_by_name: string | null;
            /** Produced Qty */
            produced_qty: number | null;
            /** Restart Reason Id */
            restart_reason_id: number | null;
            /** Restart Reason Name */
            restart_reason_name: string | null;
            /** Equipment Id */
            equipment_id?: number | null;
            /** Equipment Name */
            equipment_name?: string | null;
        };
        /** RunInputOut */
        RunInputOut: {
            /** Id */
            id: number;
            /** Kitting No */
            kitting_no: string;
            /** Lot No */
            lot_no: string;
            /** Kind */
            kind: string;
            /** Value */
            value: string;
            /** Entered By */
            entered_by: number;
            /** Entered By Name */
            entered_by_name: string;
            /**
             * Entered At
             * Format: date-time
             */
            entered_at: string;
        };
        /** StepEndIn */
        StepEndIn: {
            /**
             * Request Id
             * @description 操作ごとに一意のID。再送には同じIDを使う
             */
            request_id: string;
            /** Produced Qty */
            produced_qty?: number | null;
            /** Operator Id */
            operator_id?: number | null;
        };
        /**
         * StepResultOut
         * @description 工程の開始・終了の結果。片付けの終了では、作った完了の記録も返す。
         */
        StepResultOut: {
            event: components["schemas"]["RunEventOut"];
            completion?: components["schemas"]["RunCompletionOut"] | null;
        };
        /** StepStartIn */
        StepStartIn: {
            /**
             * Request Id
             * @description 操作ごとに一意のID。再送には同じIDを使う
             */
            request_id: string;
            /** Restart Reason Id */
            restart_reason_id?: number | null;
            /** Equipment Id */
            equipment_id?: number | null;
            /** Operator Id */
            operator_id?: number | null;
        };
        /**
         * StepType
         * @enum {string}
         */
        StepType: "setup" | "n1_check" | "production" | "first_article" | "xray" | "cleanup";
        /** SyncRunOut */
        SyncRunOut: {
            /** Id */
            id: number;
            /**
             * Started At
             * Format: date-time
             */
            started_at: string;
            /**
             * Finished At
             * Format: date-time
             */
            finished_at: string;
            /** Result */
            result: string;
            /** Added */
            added: number;
            /** Revived */
            revived: number;
            /** Changed */
            changed: number;
            /** Unchanged */
            unchanged: number;
            /** Cancelled */
            cancelled: number;
            /** Error Message */
            error_message: string | null;
            /** Legacy Dbs */
            legacy_dbs: {
                [key: string]: unknown;
            } | null;
        };
        /** SyncStatusOut */
        SyncStatusOut: {
            last_run: components["schemas"]["SyncRunOut"] | null;
            /** Warning Count */
            warning_count: number;
        };
        /** ValidationError */
        ValidationError: {
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
            /** Input */
            input?: unknown;
            /** Context */
            ctx?: Record<string, never>;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    health_api_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    list_line_plans_api_lines__line_code__plans_get: {
        parameters: {
            query?: {
                /** @description YYYY-MM-DD。省略すると今日 */
                date?: string | null;
            };
            header?: never;
            path: {
                line_code: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PlanOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    sync_status_api_sync_status_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SyncStatusOut"];
                };
            };
        };
    };
    start_step_api_runs__kitting_no___lot_no__steps__step_type__start_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                kitting_no: string;
                lot_no: string;
                step_type: components["schemas"]["StepType"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StepStartIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StepResultOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    end_step_api_runs__kitting_no___lot_no__steps__step_type__end_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                kitting_no: string;
                lot_no: string;
                step_type: components["schemas"]["StepType"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StepEndIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StepResultOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_ng_qty_api_runs__kitting_no___lot_no__ng_qty_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                kitting_no: string;
                lot_no: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["NgQtyIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunInputOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    add_remark_api_runs__kitting_no___lot_no__remarks_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                kitting_no: string;
                lot_no: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RemarkIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunInputOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_operator_api_lines__line_code__operator_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                line_code: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CurrentOperatorOut"] | null;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    change_operator_api_lines__line_code__operator_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                line_code: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ChangeOperatorIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CurrentOperatorOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    start_line_event_api_lines__line_code__events_start_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                line_code: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LineEventStartIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LineEventOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    end_line_event_api_lines__line_code__events__event_id__end_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                line_code: string;
                event_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LineEventEndIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LineEventOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_board_api_lines__line_code__board_get: {
        parameters: {
            query?: {
                /** @description YYYY-MM-DD。省略すると今日 */
                date?: string | null;
            };
            header?: never;
            path: {
                line_code: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BoardOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_masters_api_masters_get: {
        parameters: {
            query?: {
                /** @description 指定すると、設備はそのラインのものだけ */
                line_code?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MastersOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}
