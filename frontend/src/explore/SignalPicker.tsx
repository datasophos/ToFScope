import { useEffect, useState } from "react";

export type SignalOption = { index: number; label: string; mass: number };

export function SignalPicker({
  options,
  value,
  buttonLabel,
  listboxLabel,
  placeholder,
  onChoose,
}: {
  options: SignalOption[];
  value?: number;
  buttonLabel: string;
  listboxLabel: string;
  placeholder: string;
  onChoose: (index: number) => void;
}) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open]);
  const selected = options.find((option) => option.index === value);
  return (
    <div className="signal-picker">
      <button
        type="button"
        className="signal-picker-trigger"
        aria-label={buttonLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((shown) => !shown)}
      >
        <span>{selected ? `${selected.label} · ${selected.mass} Th` : placeholder}</span>
        <span aria-hidden="true">▾</span>
      </button>
      {open && (
        <div role="listbox" aria-label={listboxLabel} className="signal-picker-list">
          {options.length === 0 ? (
            <div className="signal-picker-empty">No matching signals</div>
          ) : (
            options.map((option) => (
              <button
                type="button"
                role="option"
                aria-selected={option.index === value}
                key={option.index}
                onClick={() => {
                  onChoose(option.index);
                  setOpen(false);
                }}
              >
                {option.label} · {option.mass} Th
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
