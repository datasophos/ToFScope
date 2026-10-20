import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
export function ToolPopover({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const root = useRef<HTMLElement>(null);
  const [anchor] = useState(() => {
    const b = document.activeElement?.getBoundingClientRect();
    return {
      left: Math.max(12, Math.min(b?.left ?? 20, window.innerWidth - 420)),
      top: Math.max(12, Math.min(b?.bottom ?? 80, window.innerHeight - 360)),
    };
  });
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    root.current?.querySelector<HTMLElement>("input,button")?.focus();
    return () => {
      if (previous?.isConnected) previous.focus();
    };
  }, []);
  return createPortal(
    <section
      style={anchor}
      role="dialog"
      aria-label={title}
      className="tool-popover"
      ref={root}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.stopPropagation();
          onClose();
        }
      }}
    >
      <div className="row">
        <h2>{title}</h2>
        <button aria-label={`Close ${title}`} onClick={onClose}>
          ×
        </button>
      </div>
      {children}
    </section>,
    document.body,
  );
}
