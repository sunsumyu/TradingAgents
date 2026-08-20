import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

// Global error handler — shows error overlay instead of black screen
window.onerror = (msg, _source, _lineno, _colno, err) => {
  const detail = err ? `${err.message}\n${err.stack}` : String(msg);
  document.getElementById("root")!.innerHTML = `
    <div style="padding:40px;color:#F23645;font-family:monospace;white-space:pre-wrap;background:#131722;height:100vh;overflow:auto">
      <h2 style="color:#F23645">⚠️ 启动错误</h2>
      <pre style="color:#D1D4DC;font-size:13px">${detail}</pre>
    </div>`;
};
window.onunhandledrejection = (e) => {
  const detail = e.reason?.stack || String(e.reason);
  document.getElementById("root")!.innerHTML = `
    <div style="padding:40px;color:#F23645;font-family:monospace;white-space:pre-wrap;background:#131722;height:100vh;overflow:auto">
      <h2 style="color:#F23645">⚠️ 未捕获的 Promise 错误</h2>
      <pre style="color:#D1D4DC;font-size:13px">${detail}</pre>
    </div>`;
};

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
