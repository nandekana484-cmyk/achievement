import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Dashboard } from "./field/Dashboard";
import { LineScreen } from "./field/LineScreen";
import "./shared/base.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/field" replace />} />
        <Route path="/field" element={<Dashboard />} />
        <Route path="/field/lines/:lineCode" element={<LineScreen />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
);
