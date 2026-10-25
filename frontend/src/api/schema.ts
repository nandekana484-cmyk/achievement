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
         * @description 稼働日(day_start〜翌日の day_start)に重なる計画のまとまり(キッティングNo.ごと)を、計画開始の順で返す。
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
    "/api/plans/search": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Search Plans
         * @description 一部一致で探し、当たったキッティングNo.のまとまりを返す(大文字・小文字、全角・半角は無視。最大20件)。
         */
        get: operations["search_plans_api_plans_search_get"];
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
    "/api/runs/{kitting_no}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Run
         * @description 計画のまとまり1件の工程の記録・生産数・NG数・完了・進捗率(表示範囲の外の計画を選んだときに使う)。
         */
        get: operations["get_run_api_runs__kitting_no__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/runs/{kitting_no}/steps/{step_type}/start": {
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
        post: operations["start_step_api_runs__kitting_no__steps__step_type__start_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/runs/{kitting_no}/steps/{step_type}/end": {
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
        post: operations["end_step_api_runs__kitting_no__steps__step_type__end_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/runs/{kitting_no}/ng-qty": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Set Ng Qty
         * @description NG数を、ロットとNGが出た面を選んで入力する(同じロット・面では最新の値を有効とする)。
         */
        put: operations["set_ng_qty_api_runs__kitting_no__ng_qty_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/runs/{kitting_no}/remarks": {
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
        post: operations["add_remark_api_runs__kitting_no__remarks_post"];
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
         * @description ラインの今の担当者を交代する(operator_id か worker_id のどちらかで指定)。
         */
        put: operations["change_operator_api_lines__line_code__operator_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/operators/lookup": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Lookup Operator
         * @description 作業者IDで、有効な作業者を呼び出す(無ければ 404「作業者IDが見つかりません」)。
         */
        get: operations["lookup_operator_api_operators_lookup_get"];
        put?: never;
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
         * @description ライン画面用: 表示範囲の計画ごとの工程の記録・生産数・NG数・完了・進捗率と、付帯作業、今の担当者。
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
    "/api/runs/{kitting_no}/events/{event_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Correct Run Event
         * @description 工程の記録の開始・終了の時刻と、生産の区切りの生産数を直す(理由が必須)。
         */
        patch: operations["correct_run_event_api_runs__kitting_no__events__event_id__patch"];
        trace?: never;
    };
    "/api/runs/{kitting_no}/events/{event_id}/void": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Void Run Event
         * @description 工程の記録を取り消す(記録は消さない。生産数・進捗・完了・タイムテーブルの計算から外す)。
         */
        post: operations["void_run_event_api_runs__kitting_no__events__event_id__void_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/runs/{kitting_no}/events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Add Run Event
         * @description 押し忘れた工程を後から記録する(後から足した印が付く)。
         */
        post: operations["add_run_event_api_runs__kitting_no__events_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/runs/{kitting_no}/corrections": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Kitting Corrections
         * @description 計画のまとまりの工程の記録の訂正の履歴(新しい順)。
         */
        get: operations["kitting_corrections_api_runs__kitting_no__corrections_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/lines/{line_code}/events/{event_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Correct Line Event
         * @description 付帯作業の開始・終了の時刻と、理由(設備・記入)を直す(訂正の理由が必須)。
         */
        patch: operations["correct_line_event_api_lines__line_code__events__event_id__patch"];
        trace?: never;
    };
    "/api/lines/{line_code}/events/{event_id}/void": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Void Line Event
         * @description 付帯作業を取り消す(記録は消さない)。
         */
        post: operations["void_line_event_api_lines__line_code__events__event_id__void_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/lines/{line_code}/corrections": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Line Event Corrections Of Day
         * @description 付帯作業の訂正の履歴(付帯作業の開始がその稼働日にあるもの。新しい順)。
         */
        get: operations["line_event_corrections_of_day_api_lines__line_code__corrections_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Login
         * @description 作業者IDとパスワードでログインする。失敗の理由は区別しない(401「作業者IDかパスワードが違います」)。
         */
        post: operations["login_api_admin_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Logout
         * @description ログアウトする(ログインしていなくてもよい)。
         */
        post: operations["logout_api_admin_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Me
         * @description ログイン中の管理者(ログインしていなければ 401)。
         */
        get: operations["me_api_admin_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/password": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Change Password
         * @description 自分のパスワードを変える(今のパスワードが要る。8文字以上)。ほかのセッションは無効になる。
         */
        put: operations["change_password_api_admin_password_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/equipment": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Equipment
         * @description 設備の一覧(無効なものも含む)。
         */
        get: operations["list_equipment_api_admin_equipment_get"];
        put?: never;
        /**
         * Add Equipment
         * @description 設備を追加する。
         */
        post: operations["add_equipment_api_admin_equipment_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/equipment/{equipment_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update Equipment
         * @description 設備の名前(日本語・ベトナム語)・並び順を変える。active=false で無効にする(消さない)。
         */
        patch: operations["update_equipment_api_admin_equipment__equipment_id__patch"];
        trace?: never;
    };
    "/api/admin/reasons": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Reasons
         * @description 理由の一覧(無効なものも含む)。
         */
        get: operations["list_reasons_api_admin_reasons_get"];
        put?: never;
        /**
         * Add Reason
         * @description 理由を追加する。
         */
        post: operations["add_reason_api_admin_reasons_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/reasons/{reason_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update Reason
         * @description 理由の名前・区分・入力の決まり・使い道・稼働率に含めるか・並び順を変える。active=false で無効にする。
         */
        patch: operations["update_reason_api_admin_reasons__reason_id__patch"];
        trace?: never;
    };
    "/api/admin/lines": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Lines
         * @description ラインの一覧(無効なものも含む)。
         */
        get: operations["list_lines_api_admin_lines_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/lines/{line_code}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update Line
         * @description ラインの名前・並び順を変える。active=false で無効にする。
         */
        patch: operations["update_line_api_admin_lines__line_code__patch"];
        trace?: never;
    };
    "/api/admin/operators": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Operators
         * @description 作業者の一覧(見るだけ。既存アプリから読み込む)。
         */
        get: operations["list_operators_api_admin_operators_get"];
        put?: never;
        /**
         * Add Operator
         * @description 開発用の作業者を足す(legacy_app_dir が設定されていない環境だけ)。
         */
        post: operations["add_operator_api_admin_operators_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/reports/intervals.csv": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Intervals Csv
         * @description 区間の CSV(1行 = 1つの区間。BOM 付きの UTF-8、CRLF)。期間の上限は config.toml の [reports] max_days。
         */
        get: operations["intervals_csv_api_admin_reports_intervals_csv_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/reports/daily": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Daily
         * @description 日報の表示に要る値(区間、上段・下段の棒、生産数とNG数の合計)。
         */
        get: operations["daily_api_admin_reports_daily_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/actuals": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Actuals
         * @description 書き出しの一覧(片付けが終わった計画。1行 = キッティングNo.+ロットNo.)。
         */
        get: operations["list_actuals_api_admin_actuals_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/actuals/export": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Export
         * @description 直した数を確かめて CSV を書き出し、履歴を残す。ロットの合計が累計と合わなければ 409。
         */
        post: operations["export_api_admin_actuals_export_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/actuals/exports": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Exports
         * @description 書き出しの履歴(新しい順に50件)。
         */
        get: operations["exports_api_admin_actuals_exports_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/actuals/exports/{export_id}/file": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Export File
         * @description 書き出した CSV のダウンロード(保存したものと同じ中身)。
         */
        get: operations["export_file_api_admin_actuals_exports__export_id__file_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/actuals/links": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Confirm Link
         * @description ひも付けの確認: 面1の計画のロットを面2の計画に確定する(やり直しは新しい行で上書き)。選べない面2なら 409。
         */
        post: operations["confirm_link_api_admin_actuals_links_post"];
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
        /** ActualsListOut */
        ActualsListOut: {
            /**
             * Date From
             * Format: date
             */
            date_from: string;
            /**
             * Date To
             * Format: date
             */
            date_to: string;
            /** Line Code */
            line_code: string | null;
            /** Rows */
            rows: components["schemas"]["ActualsRowOut"][];
            /** Link Checks */
            link_checks: components["schemas"]["LinkCheckOut"][];
            /** Pending Links */
            pending_links: number;
        };
        /** ActualsRowOut */
        ActualsRowOut: {
            /** Kitting No */
            kitting_no: string;
            /** Lot No */
            lot_no: string;
            /** File No */
            file_no: string;
            /** Side */
            side: number;
            /** Line Code */
            line_code: string;
            /** Product Name */
            product_name: string;
            /** Planned Qty */
            planned_qty: number;
            /** Produced Qty */
            produced_qty: number;
            /** Kitting Produced Total */
            kitting_produced_total: number;
            /** Kitting Hidden Qty */
            kitting_hidden_qty: number;
            /** Ng Side1 */
            ng_side1: number;
            /** Ng Side2 */
            ng_side2: number;
            /** Worker Id */
            worker_id: string | null;
            /** Operator Name */
            operator_name: string | null;
            /**
             * Completed On
             * Format: date
             */
            completed_on: string;
            /** Source Db */
            source_db: string | null;
            /** Side1 Kitting No */
            side1_kitting_no: string | null;
            /** Exportable */
            exportable: boolean;
            /** Warnings */
            warnings: string[];
            /** Notes */
            notes: string[];
        };
        /** AdminMeOut */
        AdminMeOut: {
            /** Operator Id */
            operator_id: number;
            /** Worker Id */
            worker_id: string | null;
            /** Name */
            name: string;
            /** Idle Minutes */
            idle_minutes: number;
            /**
             * Server Time
             * Format: date-time
             */
            server_time: string;
            /**
             * Workday
             * Format: date
             */
            workday: string;
        };
        /** BarOut */
        BarOut: {
            /** Half */
            half: number;
            /**
             * Start
             * Format: date-time
             */
            start: string;
            /**
             * End
             * Format: date-time
             */
            end: string;
            /** Step Type */
            step_type: string | null;
            /** Label */
            label: string;
            /** Open */
            open: boolean;
        };
        /** BoardOut */
        BoardOut: {
            /** Line Code */
            line_code: string;
            /**
             * Date
             * Format: date
             */
            date: string;
            /**
             * Workday Start
             * Format: date-time
             */
            workday_start: string;
            /**
             * Workday End
             * Format: date-time
             */
            workday_end: string;
            /**
             * Display Start
             * Format: date-time
             */
            display_start: string;
            /**
             * Display End
             * Format: date-time
             */
            display_end: string;
            /**
             * Server Time
             * Format: date-time
             */
            server_time: string;
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
            plan: components["schemas"]["KittingPlanOut"];
            /** Events */
            events: components["schemas"]["RunEventOut"][];
            /** Produced Qty */
            produced_qty: number;
            /** Ng Entries */
            ng_entries: components["schemas"]["NgEntryOut"][];
            /** Ng Choices */
            ng_choices: components["schemas"]["NgChoiceOut"][];
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
            operator_id?: number | null;
            /**
             * Worker Id
             * @description 作業者ID(全角・半角、大文字・小文字は区別しない)
             */
            worker_id?: string | null;
        };
        /** CorrectionChangeOut */
        CorrectionChangeOut: {
            /** Field */
            field: string;
            /** Before */
            before: string | number | boolean | null;
            /** After */
            after: string | number | boolean | null;
            /** Before Name */
            before_name?: string | null;
            /** After Name */
            after_name?: string | null;
            /** Before Name Vi */
            before_name_vi?: string | null;
            /** After Name Vi */
            after_name_vi?: string | null;
        };
        /** CorrectionOut */
        CorrectionOut: {
            /** Id */
            id: number;
            /** Target Table */
            target_table: string;
            /** Target Id */
            target_id: number;
            /** Kitting No */
            kitting_no: string | null;
            /** Line Code */
            line_code: string;
            /** Kind */
            kind: string;
            /** Changes */
            changes: components["schemas"]["CorrectionChangeOut"][];
            /** Reason */
            reason: string;
            /** Reason Label */
            reason_label: string;
            /** Note */
            note: string | null;
            /** Corrected By */
            corrected_by: number;
            /** Corrected By Name */
            corrected_by_name: string;
            /** Corrected By Worker Id */
            corrected_by_worker_id: string | null;
            /**
             * Corrected At
             * Format: date-time
             */
            corrected_at: string;
            /** Source */
            source: string;
            /** Step Type */
            step_type: string | null;
            /** Seq */
            seq: number | null;
            /** Line Event Reason Name */
            line_event_reason_name: string | null;
            /** Line Event Reason Name Vi */
            line_event_reason_name_vi: string | null;
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
            /** Operator Worker Id */
            operator_worker_id?: string | null;
        };
        /** DailyReportOut */
        DailyReportOut: {
            line: components["schemas"]["LineOut"];
            /**
             * Date
             * Format: date
             */
            date: string;
            /**
             * Workday Start
             * Format: date-time
             */
            workday_start: string;
            /**
             * Workday End
             * Format: date-time
             */
            workday_end: string;
            /** Halves */
            halves: components["schemas"]["HalfOut"][];
            /**
             * Generated At
             * Format: date-time
             */
            generated_at: string;
            /** Produced Total */
            produced_total: number;
            /** Ng Total */
            ng_total: number;
            /** Rows */
            rows: components["schemas"]["RowOut"][];
            /** Intervals */
            intervals: components["schemas"]["IntervalOut"][];
        };
        /** EquipmentAdminOut */
        EquipmentAdminOut: {
            /** Id */
            id: number;
            /** Line Code */
            line_code: string;
            /** Name */
            name: string;
            /** Name Vi */
            name_vi: string | null;
            /** Sort Order */
            sort_order: number;
            /** Active */
            active: boolean;
        };
        /** EquipmentIn */
        EquipmentIn: {
            /** Line Code */
            line_code: string;
            /** Name */
            name: string;
            /** Name Vi */
            name_vi?: string | null;
            /** Sort Order */
            sort_order?: number | null;
        };
        /** EquipmentOut */
        EquipmentOut: {
            /** Id */
            id: number;
            /** Line Code */
            line_code: string;
            /** Name */
            name: string;
            /** Name Vi */
            name_vi?: string | null;
            /** Sort Order */
            sort_order: number;
        };
        /** EquipmentPatch */
        EquipmentPatch: {
            /** Name */
            name?: string | null;
            /** Name Vi */
            name_vi?: string | null;
            /** Sort Order */
            sort_order?: number | null;
            /** Active */
            active?: boolean | null;
        };
        /** ExportIn */
        ExportIn: {
            /**
             * Date From
             * Format: date
             */
            date_from: string;
            /**
             * Date To
             * Format: date
             */
            date_to: string;
            /** Line Code */
            line_code?: string | null;
            /**
             * Quantities
             * @description 直した行だけ送る(送らない行は割り振ったまま)
             */
            quantities?: components["schemas"]["QuantityIn"][];
        };
        /** ExportOut */
        ExportOut: {
            /** Id */
            id: number;
            /**
             * Exported At
             * Format: date-time
             */
            exported_at: string;
            /** Exported By */
            exported_by: string;
            /** Row Count */
            row_count: number;
            /** File Name */
            file_name: string;
            /**
             * Date From
             * Format: date
             */
            date_from: string;
            /**
             * Date To
             * Format: date
             */
            date_to: string;
            /** Line Code */
            line_code: string | null;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** HalfOut */
        HalfOut: {
            /**
             * Start
             * Format: date-time
             */
            start: string;
            /**
             * End
             * Format: date-time
             */
            end: string;
        };
        /** IntervalOut */
        IntervalOut: {
            /**
             * Workday
             * Format: date
             */
            workday: string;
            /** Line Code */
            line_code: string;
            /** Kind */
            kind: string;
            /** Event Id */
            event_id: number;
            /** Kitting No */
            kitting_no: string | null;
            /** Lot Nos */
            lot_nos: string;
            /** File No */
            file_no: string | null;
            /** Product Names */
            product_names: string;
            /** Run No */
            run_no: number | null;
            /** Step Type */
            step_type: string | null;
            /** What */
            what: string;
            /** Restart Reason */
            restart_reason: string | null;
            /** Equipment */
            equipment: string | null;
            /** Reason Text */
            reason_text: string | null;
            /**
             * Original Start
             * Format: date-time
             */
            original_start: string;
            /** Original End */
            original_end: string | null;
            /**
             * Start
             * Format: date-time
             */
            start: string;
            /** End */
            end: string | null;
            /** Minutes */
            minutes: number;
            /** Produced Qty */
            produced_qty: number | null;
            /** Started By */
            started_by: string;
            /** Ended By */
            ended_by: string | null;
            /** Added Later */
            added_later: boolean;
            /** Corrected */
            corrected: boolean;
            /** Open */
            open: boolean;
        };
        /**
         * KittingPlanOut
         * @description 計画のまとまり(キッティングNo.ごと)。計画数はロットの数量の合計。
         */
        KittingPlanOut: {
            /** Kitting No */
            kitting_no: string;
            /** File No */
            file_no: string;
            /** Line Code */
            line_code: string;
            /** Run No */
            run_no: number;
            /** Product Name */
            product_name: string;
            /** Planned Qty */
            planned_qty: number;
            /** Planned Start */
            planned_start: string | null;
            /** Planned End */
            planned_end: string | null;
            /** Deadline */
            deadline: string | null;
            /**
             * Issue Date
             * Format: date
             */
            issue_date: string;
            /** Issue Seq */
            issue_seq: number;
            /** Status */
            status: string;
            /** Takt Sec */
            takt_sec: number | null;
            /** Source Db */
            source_db: string | null;
            /** Lots */
            lots: components["schemas"]["LotOut"][];
            /** Warnings */
            warnings: string[];
        };
        /** LineAdminOut */
        LineAdminOut: {
            /** Line Code */
            line_code: string;
            /** Name */
            name: string;
            /** Sort Order */
            sort_order: number;
            /** Active */
            active: boolean;
            /** Auto Named */
            auto_named: boolean;
        };
        /**
         * LineEventCorrectIn
         * @description 付帯作業の訂正。直す項目だけ送る。
         */
        LineEventCorrectIn: {
            /** Operator Id */
            operator_id?: number | null;
            /**
             * Worker Id
             * @description 作業者ID(全角・半角、大文字・小文字は区別しない)
             */
            worker_id?: string | null;
            /**
             * Request Id
             * @description 操作ごとに一意のID。再送には同じIDを使う
             */
            request_id: string;
            /** Reason */
            reason: string;
            /** Note */
            note?: string | null;
            /** Start At */
            start_at?: string | null;
            /** End At */
            end_at?: string | null;
            /** Reason Id */
            reason_id?: number | null;
            /** Equipment Id */
            equipment_id?: number | null;
            /** Reason Text */
            reason_text?: string | null;
        };
        /** LineEventCorrectionResultOut */
        LineEventCorrectionResultOut: {
            correction: components["schemas"]["CorrectionOut"];
            event: components["schemas"]["LineEventOut"];
        };
        /** LineEventEndIn */
        LineEventEndIn: {
            /** Operator Id */
            operator_id?: number | null;
            /**
             * Worker Id
             * @description 作業者ID(全角・半角、大文字・小文字は区別しない)
             */
            worker_id?: string | null;
            /**
             * Request Id
             * @description 操作ごとに一意のID。再送には同じIDを使う
             */
            request_id: string;
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
            /** Reason Name Vi */
            reason_name_vi?: string | null;
            /** Equipment Name Vi */
            equipment_name_vi?: string | null;
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
            /** Started By Worker Id */
            started_by_worker_id?: string | null;
            /** Ended By Worker Id */
            ended_by_worker_id?: string | null;
            /** Voided At */
            voided_at?: string | null;
            /** Voided By Name */
            voided_by_name?: string | null;
            /** Voided By Worker Id */
            voided_by_worker_id?: string | null;
            /** Void Reason */
            void_reason?: string | null;
        };
        /** LineEventStartIn */
        LineEventStartIn: {
            /** Operator Id */
            operator_id?: number | null;
            /**
             * Worker Id
             * @description 作業者ID(全角・半角、大文字・小文字は区別しない)
             */
            worker_id?: string | null;
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
        };
        /** LineOut */
        LineOut: {
            /** Line Code */
            line_code: string;
            /** Name */
            name: string;
            /** Sort Order */
            sort_order: number;
            /**
             * Auto Named
             * @default false
             */
            auto_named: boolean;
        };
        /** LinePatch */
        LinePatch: {
            /** Name */
            name?: string | null;
            /** Sort Order */
            sort_order?: number | null;
            /** Active */
            active?: boolean | null;
        };
        /** LinkCandidateOut */
        LinkCandidateOut: {
            /** Kitting No */
            kitting_no: string;
            /**
             * Issue Date
             * Format: date
             */
            issue_date: string;
            /** Paired With */
            paired_with: string | null;
        };
        /**
         * LinkCheckOut
         * @description ひも付けの確認の1行(面1の計画のロットごと)。
         */
        LinkCheckOut: {
            /** Lot No */
            lot_no: string;
            /** File No */
            file_no: string;
            /** Side1 Kitting No */
            side1_kitting_no: string;
            /**
             * Side1 Issue Date
             * Format: date
             */
            side1_issue_date: string;
            /** Side1 Completed */
            side1_completed: boolean;
            /**
             * State
             * @enum {string}
             */
            state: "pending" | "confirmed" | "unlinked";
            /** Side2 Kitting No */
            side2_kitting_no: string | null;
            /** Decided By */
            decided_by: string | null;
            /** Decided At */
            decided_at: string | null;
            /** Suggested */
            suggested: string | null;
            /** Candidates */
            candidates: components["schemas"]["LinkCandidateOut"][];
        };
        /** LinkIn */
        LinkIn: {
            /** Lot No */
            lot_no: string;
            /**
             * Side1 Kitting No
             * @description 面1の計画
             */
            side1_kitting_no: string;
            /**
             * Side2 Kitting No
             * @description 面2の計画。空(null)は「つながない」
             */
            side2_kitting_no?: string | null;
        };
        /** LoginIn */
        LoginIn: {
            /** Worker Id */
            worker_id: string;
            /** Password */
            password: string;
        };
        /**
         * LotOut
         * @description まとまり(キッティングNo.)の中のロット(確認用)。
         */
        LotOut: {
            /** Lot No */
            lot_no: string;
            /** Product Name */
            product_name: string;
            /** Planned Qty */
            planned_qty: number;
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
        /**
         * NgChoiceOut
         * @description ロットごとの、NGを入力できる面。
         */
        NgChoiceOut: {
            /** Lot No */
            lot_no: string;
            /** Sides */
            sides: number[];
            /** Side1 Kitting No */
            side1_kitting_no: string | null;
            /** Note */
            note: string | null;
        };
        /**
         * NgEntryOut
         * @description ロットと面ごとの、最新のNG数。
         */
        NgEntryOut: {
            /** Lot No */
            lot_no: string;
            /** Side */
            side: number;
            /** Side Kitting No */
            side_kitting_no: string;
            /** Ng Qty */
            ng_qty: number;
            /**
             * Entered By Name
             * @default
             */
            entered_by_name: string;
            /** Entered At */
            entered_at?: string | null;
            /** Entered By Worker Id */
            entered_by_worker_id?: string | null;
        };
        /**
         * NgInputOut
         * @description NG数の入力の結果。
         */
        NgInputOut: {
            /** Id */
            id: number;
            /** Kitting No */
            kitting_no: string;
            /** Lot No */
            lot_no: string;
            /** Side */
            side: number;
            /** Side Kitting No */
            side_kitting_no: string;
            /** Ng Qty */
            ng_qty: number;
            /** Entered By */
            entered_by: number;
            /** Entered By Name */
            entered_by_name: string;
            /**
             * Entered At
             * Format: date-time
             */
            entered_at: string;
            /** Entered By Worker Id */
            entered_by_worker_id?: string | null;
        };
        /** NgQtyIn */
        NgQtyIn: {
            /** Operator Id */
            operator_id?: number | null;
            /**
             * Worker Id
             * @description 作業者ID(全角・半角、大文字・小文字は区別しない)
             */
            worker_id?: string | null;
            /**
             * Request Id
             * @description 操作ごとに一意のID。再送には同じIDを使う
             */
            request_id: string;
            /** Lot No */
            lot_no: string;
            /** Side */
            side: number;
            /** Ng Qty */
            ng_qty: number;
        };
        /** OperatorAdminOut */
        OperatorAdminOut: {
            /** Id */
            id: number;
            /** Name */
            name: string;
            /** Worker Id */
            worker_id: string | null;
            /** Role */
            role: string;
            /** Active */
            active: boolean;
            /** Source */
            source: string;
            /** Has Password */
            has_password: boolean;
        };
        /** OperatorIn */
        OperatorIn: {
            /** Name */
            name: string;
            /** Worker Id */
            worker_id?: string | null;
        };
        /** OperatorOut */
        OperatorOut: {
            /** Id */
            id: number;
            /** Name */
            name: string;
            /** Worker Id */
            worker_id: string | null;
            /** Sort Order */
            sort_order: number;
        };
        /** PasswordChangeIn */
        PasswordChangeIn: {
            /** Current Password */
            current_password: string;
            /** New Password */
            new_password: string;
        };
        /** QuantityIn */
        QuantityIn: {
            /** Kitting No */
            kitting_no: string;
            /** Lot No */
            lot_no: string;
            /**
             * Produced Qty
             * @description 画面で直した生産数(累計)
             */
            produced_qty: number;
        };
        /** ReasonAdminOut */
        ReasonAdminOut: {
            /** Id */
            id: number;
            /** Name */
            name: string;
            /** Name Vi */
            name_vi: string | null;
            /** Category */
            category: string;
            /** Requires Equipment */
            requires_equipment: boolean;
            /** Requires Text */
            requires_text: boolean;
            /** Usable As Line Event */
            usable_as_line_event: boolean;
            /** Usable As Restart */
            usable_as_restart: boolean;
            /** Counts In Utilization */
            counts_in_utilization: boolean;
            /** Sort Order */
            sort_order: number;
            /** Active */
            active: boolean;
        };
        /** ReasonIn */
        ReasonIn: {
            /** Name */
            name: string;
            /** Name Vi */
            name_vi?: string | null;
            /**
             * Category
             * @default loss
             */
            category: string;
            /**
             * Requires Equipment
             * @default false
             */
            requires_equipment: boolean;
            /**
             * Requires Text
             * @default false
             */
            requires_text: boolean;
            /**
             * Usable As Line Event
             * @default false
             */
            usable_as_line_event: boolean;
            /**
             * Usable As Restart
             * @default false
             */
            usable_as_restart: boolean;
            /**
             * Counts In Utilization
             * @default false
             */
            counts_in_utilization: boolean;
            /** Sort Order */
            sort_order?: number | null;
        };
        /** ReasonOut */
        ReasonOut: {
            /** Id */
            id: number;
            /** Name */
            name: string;
            /** Name Vi */
            name_vi?: string | null;
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
        /** ReasonPatch */
        ReasonPatch: {
            /** Name */
            name?: string | null;
            /** Name Vi */
            name_vi?: string | null;
            /** Category */
            category?: string | null;
            /** Requires Equipment */
            requires_equipment?: boolean | null;
            /** Requires Text */
            requires_text?: boolean | null;
            /** Usable As Line Event */
            usable_as_line_event?: boolean | null;
            /** Usable As Restart */
            usable_as_restart?: boolean | null;
            /** Counts In Utilization */
            counts_in_utilization?: boolean | null;
            /** Sort Order */
            sort_order?: number | null;
            /** Active */
            active?: boolean | null;
        };
        /** RemarkIn */
        RemarkIn: {
            /** Operator Id */
            operator_id?: number | null;
            /**
             * Worker Id
             * @description 作業者ID(全角・半角、大文字・小文字は区別しない)
             */
            worker_id?: string | null;
            /**
             * Request Id
             * @description 操作ごとに一意のID。再送には同じIDを使う
             */
            request_id: string;
            /** Text */
            text: string;
        };
        /** RowOut */
        RowOut: {
            /** Kind */
            kind: string;
            /** Kitting No */
            kitting_no: string | null;
            /** Product Names */
            product_names: string;
            /** Bars */
            bars: components["schemas"]["BarOut"][];
        };
        /** RunCompletionOut */
        RunCompletionOut: {
            /** Id */
            id: number;
            /** Kitting No */
            kitting_no: string;
            /**
             * Completed At
             * Format: date-time
             */
            completed_at: string;
            /** Produced Qty */
            produced_qty: number;
            /** Plan Qty Snapshot */
            plan_qty_snapshot: number;
            /** Takt Sec Snapshot */
            takt_sec_snapshot: number | null;
            /** Lots Snapshot */
            lots_snapshot: components["schemas"]["LotOut"][];
            /** Ng Snapshot */
            ng_snapshot: components["schemas"]["NgEntryOut"][];
            /** Utilization */
            utilization: number | null;
            /**
             * Kind
             * @default cleanup
             */
            kind: string;
            /** Correction Id */
            correction_id?: number | null;
        };
        /**
         * RunCorrectionResultOut
         * @description 工程の記録の訂正の結果。完了した計画なら、作り直した完了も返す。
         */
        RunCorrectionResultOut: {
            correction: components["schemas"]["CorrectionOut"];
            event: components["schemas"]["RunEventOut"];
            /** Completed */
            completed: boolean;
            completion: components["schemas"]["RunCompletionOut"] | null;
        };
        /**
         * RunEventAddIn
         * @description 押し忘れた工程の後からの追加。
         */
        RunEventAddIn: {
            /** Operator Id */
            operator_id?: number | null;
            /**
             * Worker Id
             * @description 作業者ID(全角・半角、大文字・小文字は区別しない)
             */
            worker_id?: string | null;
            /**
             * Request Id
             * @description 操作ごとに一意のID。再送には同じIDを使う
             */
            request_id: string;
            /** Reason */
            reason: string;
            /** Note */
            note?: string | null;
            step_type: components["schemas"]["StepType"];
            /**
             * Start At
             * Format: date-time
             */
            start_at: string;
            /**
             * End At
             * Format: date-time
             */
            end_at: string;
            /** Produced Qty */
            produced_qty?: number | null;
        };
        /**
         * RunEventCorrectIn
         * @description 工程の記録の訂正。直す項目だけ送る(時刻はタイムゾーン付き)。
         */
        RunEventCorrectIn: {
            /** Operator Id */
            operator_id?: number | null;
            /**
             * Worker Id
             * @description 作業者ID(全角・半角、大文字・小文字は区別しない)
             */
            worker_id?: string | null;
            /**
             * Request Id
             * @description 操作ごとに一意のID。再送には同じIDを使う
             */
            request_id: string;
            /** Reason */
            reason: string;
            /** Note */
            note?: string | null;
            /** Start At */
            start_at?: string | null;
            /** End At */
            end_at?: string | null;
            /** Produced Qty */
            produced_qty?: number | null;
        };
        /** RunEventOut */
        RunEventOut: {
            /** Id */
            id: number;
            /** Kitting No */
            kitting_no: string;
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
            /** Started By Worker Id */
            started_by_worker_id?: string | null;
            /** Ended By Worker Id */
            ended_by_worker_id?: string | null;
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
            /** Restart Reason Name Vi */
            restart_reason_name_vi?: string | null;
            /** Equipment Name Vi */
            equipment_name_vi?: string | null;
            /** Voided At */
            voided_at?: string | null;
            /** Voided By Name */
            voided_by_name?: string | null;
            /** Voided By Worker Id */
            voided_by_worker_id?: string | null;
            /** Void Reason */
            void_reason?: string | null;
            /**
             * Added Later
             * @default false
             */
            added_later: boolean;
        };
        /**
         * RunInputOut
         * @description 備考(キッティングNo.の単位)。
         */
        RunInputOut: {
            /** Id */
            id: number;
            /** Kitting No */
            kitting_no: string;
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
            /** Entered By Worker Id */
            entered_by_worker_id?: string | null;
        };
        /** SearchHitOut */
        SearchHitOut: {
            plan: components["schemas"]["KittingPlanOut"];
            /** Matched */
            matched: string[];
        };
        /** StepEndIn */
        StepEndIn: {
            /** Operator Id */
            operator_id?: number | null;
            /**
             * Worker Id
             * @description 作業者ID(全角・半角、大文字・小文字は区別しない)
             */
            worker_id?: string | null;
            /**
             * Request Id
             * @description 操作ごとに一意のID。再送には同じIDを使う
             */
            request_id: string;
            /** Produced Qty */
            produced_qty?: number | null;
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
            /** Operator Id */
            operator_id?: number | null;
            /**
             * Worker Id
             * @description 作業者ID(全角・半角、大文字・小文字は区別しない)
             */
            worker_id?: string | null;
            /**
             * Request Id
             * @description 操作ごとに一意のID。再送には同じIDを使う
             */
            request_id: string;
            /** Restart Reason Id */
            restart_reason_id?: number | null;
            /** Equipment Id */
            equipment_id?: number | null;
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
        /**
         * VoidIn
         * @description 記録の取り消し。
         */
        VoidIn: {
            /** Operator Id */
            operator_id?: number | null;
            /**
             * Worker Id
             * @description 作業者ID(全角・半角、大文字・小文字は区別しない)
             */
            worker_id?: string | null;
            /**
             * Request Id
             * @description 操作ごとに一意のID。再送には同じIDを使う
             */
            request_id: string;
            /** Reason */
            reason: string;
            /** Note */
            note?: string | null;
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
                /** @description 稼働日(YYYY-MM-DD)。省略すると今の稼働日 */
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
                    "application/json": components["schemas"]["KittingPlanOut"][];
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
    search_plans_api_plans_search_get: {
        parameters: {
            query: {
                /** @description キッティングNo.・ロットNo.・基板名の一部 */
                q: string;
                /** @description 指定すると、そのラインの計画だけ */
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
                    "application/json": components["schemas"]["SearchHitOut"][];
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
    get_run_api_runs__kitting_no__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                kitting_no: string;
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
                    "application/json": components["schemas"]["BoardPlanOut"];
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
    start_step_api_runs__kitting_no__steps__step_type__start_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                kitting_no: string;
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
    end_step_api_runs__kitting_no__steps__step_type__end_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                kitting_no: string;
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
    set_ng_qty_api_runs__kitting_no__ng_qty_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                kitting_no: string;
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
                    "application/json": components["schemas"]["NgInputOut"];
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
    add_remark_api_runs__kitting_no__remarks_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                kitting_no: string;
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
    lookup_operator_api_operators_lookup_get: {
        parameters: {
            query: {
                /** @description 作業者ID(全角・半角、大文字・小文字は区別しない) */
                worker_id: string;
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
                    "application/json": components["schemas"]["OperatorOut"];
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
                /** @description 稼働日(YYYY-MM-DD)。省略すると今の稼働日 */
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
    correct_run_event_api_runs__kitting_no__events__event_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                kitting_no: string;
                event_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RunEventCorrectIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunCorrectionResultOut"];
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
    void_run_event_api_runs__kitting_no__events__event_id__void_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                kitting_no: string;
                event_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["VoidIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunCorrectionResultOut"];
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
    add_run_event_api_runs__kitting_no__events_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                kitting_no: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RunEventAddIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunCorrectionResultOut"];
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
    kitting_corrections_api_runs__kitting_no__corrections_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                kitting_no: string;
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
                    "application/json": components["schemas"]["CorrectionOut"][];
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
    correct_line_event_api_lines__line_code__events__event_id__patch: {
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
                "application/json": components["schemas"]["LineEventCorrectIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LineEventCorrectionResultOut"];
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
    void_line_event_api_lines__line_code__events__event_id__void_post: {
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
                "application/json": components["schemas"]["VoidIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LineEventCorrectionResultOut"];
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
    line_event_corrections_of_day_api_lines__line_code__corrections_get: {
        parameters: {
            query?: {
                /** @description 稼働日(YYYY-MM-DD)。省略すると今の稼働日 */
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
                    "application/json": components["schemas"]["CorrectionOut"][];
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
    login_api_admin_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AdminMeOut"];
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
    logout_api_admin_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    me_api_admin_me_get: {
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
                    "application/json": components["schemas"]["AdminMeOut"];
                };
            };
        };
    };
    change_password_api_admin_password_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PasswordChangeIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
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
    list_equipment_api_admin_equipment_get: {
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
                    "application/json": components["schemas"]["EquipmentAdminOut"][];
                };
            };
        };
    };
    add_equipment_api_admin_equipment_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EquipmentIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EquipmentAdminOut"];
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
    update_equipment_api_admin_equipment__equipment_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                equipment_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EquipmentPatch"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EquipmentAdminOut"];
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
    list_reasons_api_admin_reasons_get: {
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
                    "application/json": components["schemas"]["ReasonAdminOut"][];
                };
            };
        };
    };
    add_reason_api_admin_reasons_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReasonIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReasonAdminOut"];
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
    update_reason_api_admin_reasons__reason_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                reason_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReasonPatch"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReasonAdminOut"];
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
    list_lines_api_admin_lines_get: {
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
                    "application/json": components["schemas"]["LineAdminOut"][];
                };
            };
        };
    };
    update_line_api_admin_lines__line_code__patch: {
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
                "application/json": components["schemas"]["LinePatch"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LineAdminOut"];
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
    list_operators_api_admin_operators_get: {
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
                    "application/json": components["schemas"]["OperatorAdminOut"][];
                };
            };
        };
    };
    add_operator_api_admin_operators_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["OperatorIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperatorAdminOut"];
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
    intervals_csv_api_admin_reports_intervals_csv_get: {
        parameters: {
            query: {
                /** @description 稼働日の始め(YYYY-MM-DD) */
                from: string;
                /** @description 稼働日の終わり(YYYY-MM-DD。含む) */
                to: string;
                /** @description 省略するとすべてのライン */
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
                    "text/csv": string;
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
    daily_api_admin_reports_daily_get: {
        parameters: {
            query: {
                /** @description 稼働日(YYYY-MM-DD) */
                date: string;
                /** @description ライン */
                line_code: string;
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
                    "application/json": components["schemas"]["DailyReportOut"];
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
    list_actuals_api_admin_actuals_get: {
        parameters: {
            query: {
                /** @description 完了日(稼働日)の始め(YYYY-MM-DD) */
                from: string;
                /** @description 完了日(稼働日)の終わり(YYYY-MM-DD。含む) */
                to: string;
                /** @description 省略するとすべてのライン */
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
                    "application/json": components["schemas"]["ActualsListOut"];
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
    export_api_admin_actuals_export_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ExportIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExportOut"];
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
    exports_api_admin_actuals_exports_get: {
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
                    "application/json": components["schemas"]["ExportOut"][];
                };
            };
        };
    };
    export_file_api_admin_actuals_exports__export_id__file_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                export_id: number;
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
                    "text/csv": string;
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
    confirm_link_api_admin_actuals_links_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LinkIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LinkCheckOut"];
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
