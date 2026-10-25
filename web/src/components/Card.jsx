import React from "react";
import { renderMarkdown, shapeOf } from "../md.jsx";

/** A markdown Result as a styled card: answer (מכנה … credit), refusal (# ❌ … lab line), route (# 🧭 … lab line). */
export default function Card({ text, onRoute }) {
  const shape = shapeOf(text);
  const lines = String(text || "").split("\n");
  const last = lines[lines.length - 1];
  const body = lines.slice(0, -1).join("\n");
  return (
    <div className={`card card-${shape}`}>
      <div className="card-body">{renderMarkdown(body, { onRoute })}</div>
      <div className={shape === "answer" ? "credit" : "lab-line"}>{last}</div>
    </div>
  );
}
