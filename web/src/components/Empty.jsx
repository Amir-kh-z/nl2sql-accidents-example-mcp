import React from "react";

export default function Empty({ title, text, children }) {
  return (
    <div className="empty">
      {title && <h3>{title}</h3>}
      {text && <p>{text}</p>}
      {children}
    </div>
  );
}
