import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
export function ToolPopover({
  title,
  className = "",
  children,
  onClose,
  width = 400,
  placement = "anchor",
}: {
  title: string;
  className?: string;
  children: ReactNode;
  onClose: () => void;
  width?: number;
  placement?: "anchor" | "top";
}) {
  const root = useRef<HTMLElement>(null);
  const [viewport, setViewport] = useState({
    width: window.innerWidth,
    height: window.innerHeight,
  });
  useEffect(() => {
    const resize = () =>
      setViewport({ width: window.innerWidth, height: window.innerHeight });
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);
  const [anchor] = useState(() => {
    const b = document.activeElement?.getBoundingClientRect();
    return {
      left: Math.max(
        12,
        Math.min(b?.left ?? 20, window.innerWidth - width - 20),
      ),
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
  const top =
    placement === "top"
      ? 12
      : Math.max(12, Math.min(anchor.top, viewport.height - 360));
  return createPortal(
    <section
      style={{
        left: Math.max(
          12,
          Math.min(
            anchor.left,
            viewport.width - Math.min(width, viewport.width - 24) - 12,
          ),
        ),
        top,
        maxHeight: viewport.height - top - 12,
        width,
      }}
      role="dialog"
      aria-label={title}
      className={`tool-popover ${className}`}
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
