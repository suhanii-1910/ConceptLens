import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App, { AppBoundary } from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AppBoundary>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </AppBoundary>
  </React.StrictMode>,
);
