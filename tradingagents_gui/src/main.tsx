import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

// Log + display errors for debugging
const root = document.getElementById("root")!;
window.addEventListener("error", (e) => {
  console.error("[TA Error]", e.message, e.filename, e.lineno, e.error);
  // Show error overlay but DON'T replace DOM — React can still recover
  if (!document.getElementById("error-overlay")) {
    const overlay = document.createElement("div");
    overlay.id = "error-overlay";
    overlay.style.cssText = "position:fixed;top:0;left:0;right:0;background:#1a1a2e;color:#e74c3c;padding:20px;z-index:99999;font-family:monospace;font-size:13px;border-bottom:2px solid #e74c3c;max-height:50vh;overflow:auto";
    overlay.innerHTML = `<b>⚠️ JS Error:</b><br>${e.message}<br><small>${e.filename}:${e.lineno}:${e.colno}</small><pre style="color:#aaa;white-space:pre-wrap">${e.error?.stack || ""}</pre>`;
    document.body.appendChild(overlay);
  }
});
window.addEventListener("unhandledrejection", (e) => {
  console.error("[TA Promise]", e.reason);
});

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
