import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import App from "./App";

const docRoot = document.getElementById("root");
if (!docRoot) {
  throw new Error("No document root element found");
}
const root = ReactDOM.createRoot(docRoot);
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
