import {
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

export function HelpButton({
  label,
  content,
}: {
  label: string;
  content: string;
}) {
  const id = useId();
  const button = useRef<HTMLButtonElement>(null);
  const tooltip = useRef<HTMLDivElement>(null);
  const pinned = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState({ left: 0, top: 0 });
  const show = () => {
    clearTimeout(timer.current);
    setOpen(true);
  };
  const hide = () => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      if (!pinned.current && document.activeElement !== button.current)
        setOpen(false);
    }, 150);
  };
  useEffect(() => () => clearTimeout(timer.current), []);
  useLayoutEffect(() => {
    if (!open) return;
    const place = () => {
      if (!button.current || !tooltip.current) return;
      const anchor = button.current.getBoundingClientRect();
      const box = tooltip.current.getBoundingClientRect();
      const top =
        anchor.bottom + 8 + box.height <= window.innerHeight - 12
          ? anchor.bottom + 8
          : anchor.top - box.height - 8;
      setPosition({
        left: Math.max(
          12,
          Math.min(anchor.left, window.innerWidth - box.width - 12),
        ),
        top: Math.max(12, Math.min(top, window.innerHeight - box.height - 12)),
      });
    };
    place();
    window.addEventListener("resize", place);
    document.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      document.removeEventListener("scroll", place, true);
    };
  }, [open, content]);
  useEffect(() => {
    if (!open) return;
    const dismiss = () => {
      pinned.current = false;
      setOpen(false);
    };
    const key = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      // Dismissing help must not also restore a maximized chart.
      event.stopPropagation();
      dismiss();
    };
    const outside = (event: PointerEvent) => {
      if (
        !button.current?.contains(event.target as Node) &&
        !tooltip.current?.contains(event.target as Node)
      )
        dismiss();
    };
    document.addEventListener("keydown", key, true);
    document.addEventListener("pointerdown", outside, true);
    return () => {
      document.removeEventListener("keydown", key, true);
      document.removeEventListener("pointerdown", outside, true);
    };
  }, [open]);
  return (
    <>
      <button
        ref={button}
        type="button"
        className="help-button"
        aria-label={`${label} help`}
        aria-describedby={open ? id : undefined}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={() => {
          pinned.current = false;
          hide();
        }}
        onClick={() => {
          pinned.current = !pinned.current;
          setOpen(pinned.current);
        }}
      >
        i
      </button>
      {open &&
        createPortal(
          <div
            ref={tooltip}
            id={id}
            role="tooltip"
            className="help-tooltip"
            style={position}
            onMouseEnter={show}
            onMouseLeave={hide}
          >
            {content}
          </div>,
          document.body,
        )}
    </>
  );
}

export function HelpHeading({
  title,
  content,
  children,
}: {
  title: string;
  content: string;
  children?: ReactNode;
}) {
  return (
    <div className="heading-help">
      <h2>
        {title}
        {children}
      </h2>
      <HelpButton label={title} content={content} />
    </div>
  );
}
