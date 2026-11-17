import { useEffect, useRef, type ReactNode } from "react";

export function SpectrumActions({ children }: { children: ReactNode }) {
  const root = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    const close = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node))
        root.current?.removeAttribute("open");
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && root.current?.open) {
        root.current.removeAttribute("open");
        root.current.querySelector("summary")?.focus();
      }
    };
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", escape);
    };
  }, []);
  return (
    <details ref={root} className="spectrum-actions">
      <summary>
        Analyze <span aria-hidden="true">▾</span>
      </summary>
      <div
        className="spectrum-actions-menu"
        onClick={(event) => {
          if ((event.target as HTMLElement).closest("button")) {
            root.current?.removeAttribute("open");
            root.current?.querySelector("summary")?.focus();
          }
        }}
      >
        {children}
      </div>
    </details>
  );
}
