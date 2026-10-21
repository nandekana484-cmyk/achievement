import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Dashboard } from "./field/Dashboard";
import { LineScreen } from "./field/line/LineScreen";
import { I18nProvider } from "./i18n/I18nProvider";
import "./shared/base.css";
import "./field/line/line.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <I18nProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/field" replace />} />
          <Route path="/field" element={<Dashboard />} />
          <Route path="/field/lines/:lineCode" element={<LineScreen />} />
        </Routes>
      </BrowserRouter>
    </I18nProvider>
  </React.StrictMode>,
);
