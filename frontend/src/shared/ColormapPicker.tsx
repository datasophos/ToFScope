import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { vtkColorStops } from "../volumes/vtkColors";

export type ColormapOption = { value: string; label: string; palette: string };

export function ColormapPicker({
  label,
  value,
  options,
  onChange,
  reversed = false,
}: {
  label: string;
  value: string;
  options: ColormapOption[];
  onChange: (value: string) => void;
  reversed?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [position, setPosition] = useState({
    left: 0,
    top: 0,
    width: 200,
    maxHeight: 300,
  });
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const id = useId();
  const selected = options.find((o) => o.value === value) ?? options[0];
  const gradient = (palette: string) =>
    `linear-gradient(to right, ${vtkColorStops(palette, reversed)
      .map(([p, r, g, b]) => `rgb(${r},${g},${b}) ${p * 100}%`)
      .join(",")})`;
  const choose = (index: number) => {
    onChange(options[index].value);
    setOpen(false);
    trigger.current?.focus();
  };
  const show = () => {
    setActive(
      Math.max(
        0,
        options.findIndex((o) => o.value === value),
      ),
    );
    setOpen(true);
  };
  useLayoutEffect(() => {
    if (!open) return;
    const place = () => {
      const rect = trigger.current?.getBoundingClientRect();
      if (!rect) return;
      const width = Math.min(Math.max(rect.width, 200), window.innerWidth - 16);
      const height = Math.min(options.length * 38 + 8, window.innerHeight - 16);
      const top =
        rect.bottom + height + 4 <= window.innerHeight
          ? rect.bottom + 4
          : Math.max(8, rect.top - height - 4);
      setPosition({
        left: Math.max(8, Math.min(rect.left, window.innerWidth - width - 8)),
        top,
        width,
        maxHeight: height,
      });
    };
    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [open, options.length]);
  useEffect(() => {
    if (!open) return;
    const outside = (e: PointerEvent) => {
      const node = e.target as Node;
      if (!trigger.current?.contains(node) && !menu.current?.contains(node))
        setOpen(false);
    };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open]);
  useEffect(() => {
    if (open)
      document
        .getElementById(`${id}-${active}`)
        ?.scrollIntoView({ block: "nearest" });
  }, [open, active, id]);
  return (
    <>
      <button
        ref={trigger}
        type="button"
        role="combobox"
        aria-label={label}
        aria-expanded={open}
        aria-controls={id}
        aria-haspopup="listbox"
        aria-activedescendant={open ? `${id}-${active}` : undefined}
        className="colormap-trigger"
        onClick={() => (open ? setOpen(false) : show())}
        onKeyDown={(e) => {
          if (e.key === "Escape" && open) {
            e.preventDefault();
            e.stopPropagation();
            setOpen(false);
          } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault();
            if (!open) show();
            else
              setActive(
                (i) =>
                  (i + (e.key === "ArrowDown" ? 1 : options.length - 1)) %
                  options.length,
              );
          } else if ((e.key === "Enter" || e.key === " ") && open) {
            e.preventDefault();
            choose(active);
          } else if (e.key === "Tab") setOpen(false);
        }}
      >
        <span
          className="colormap-swatch"
          style={{ backgroundImage: gradient(selected.palette) }}
          aria-hidden="true"
        />
        <span>{selected.label}</span>
        <span className="colormap-chevron" aria-hidden="true">
          ▾
        </span>
      </button>
      {open &&
        createPortal(
          <div
            ref={menu}
            id={id}
            role="listbox"
            aria-label={`${label} options`}
            className="colormap-menu"
            style={{
              position: "fixed",
              ...position,
              overflowY: "auto",
              zIndex: 110,
            }}
          >
            {options.map((option, i) => (
              <button
                type="button"
                role="option"
                id={`${id}-${i}`}
                key={option.value}
                aria-selected={option.value === value}
                className={i === active ? "active" : ""}
                onMouseEnter={() => setActive(i)}
                onClick={() => choose(i)}
              >
                <span
                  className="colormap-swatch"
                  style={{ backgroundImage: gradient(option.palette) }}
                  aria-hidden="true"
                />
                <span>{option.label}</span>
                {option.value === value && (
                  <span className="colormap-check" aria-hidden="true">
                    ✓
                  </span>
                )}
              </button>
            ))}
          </div>,
          document.body,
        )}
    </>
  );
}
