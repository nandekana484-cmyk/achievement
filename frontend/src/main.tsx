import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AccessPage } from "./admin/access/AccessPage";
import { HandoverPage } from "./admin/handover/HandoverPage";
import { TeitoriPage } from "./admin/teitori/TeitoriPage";
import { ActualsPage } from "./admin/actuals/ActualsPage";
import { AdminLayout } from "./admin/AdminLayout";
import { AdminLogin } from "./admin/AdminLogin";
import { EquipmentPage } from "./admin/EquipmentPage";
import { LinesPage } from "./admin/LinesPage";
import { OperatorsPage } from "./admin/OperatorsPage";
import { PasswordPage } from "./admin/PasswordPage";
import { ReasonsPage } from "./admin/ReasonsPage";
import { ReportsPage } from "./admin/reports/ReportsPage";
import { Dashboard } from "./field/Dashboard";
import { LineScreen } from "./field/line/LineScreen";
import { I18nProvider } from "./i18n/I18nProvider";
import "./shared/base.css";
import "./field/line/line.css";
import "./field/line/corrections/corrections.css";
import "./admin/admin.css";
import "./admin/reports/report.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <I18nProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/field" replace />} />
          <Route path="/field" element={<Dashboard />} />
          <Route path="/field/lines/:lineCode" element={<LineScreen />} />
          <Route path="/admin/login" element={<AdminLogin />} />
          <Route path="/admin" element={<AdminLayout />}>
            <Route index element={<Navigate to="equipment" replace />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="actuals" element={<ActualsPage />} />
            <Route path="equipment" element={<EquipmentPage />} />
            <Route path="reasons" element={<ReasonsPage />} />
            <Route path="lines" element={<LinesPage />} />
            <Route path="operators" element={<OperatorsPage />} />
            <Route path="access" element={<AccessPage />} />
            <Route path="teitori" element={<TeitoriPage />} />
            <Route path="handover" element={<HandoverPage />} />
            <Route path="password" element={<PasswordPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </I18nProvider>
  </React.StrictMode>,
);
