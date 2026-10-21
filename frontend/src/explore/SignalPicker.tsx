import { useEffect, useRef, useState } from "react";

export type SignalOption = { index: number; label: string; mass: number };

export function SignalPicker({
  options,
  value,
  buttonLabel,
  listboxLabel,
  placeholder,
  onChoose,
  onCreate,
  onOpen,
  createDisabled,
}: {
  options: SignalOption[];
  value?: number;
  buttonLabel: string;
  listboxLabel: string;
  placeholder: string;
  onChoose: (index: number) => void;
  onCreate?: () => void;
  onOpen?: () => void;
  createDisabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const trigger = useRef<HTMLButtonElement>(null);
  const searchInput = useRef<HTMLInputElement>(null);
  const close = () => {
    setOpen(false);
    trigger.current?.focus();
  };
  useEffect(() => {
    if (!open) return;
    searchInput.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        trigger.current?.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open]);
  const matches = options.filter((option) =>
    `${option.label} ${option.mass}`
      .toLowerCase()
      .includes(search.trim().toLowerCase()),
  );
  const selected = options.find((option) => option.index === value);
  return (
    <div className="signal-picker">
      <button
        ref={trigger}
        type="button"
        className="signal-picker-trigger"
        aria-label={buttonLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => {
          if (!open) onOpen?.();
          setSearch("");
          setOpen((shown) => !shown);
        }}
      >
        <span>
          {selected ? `${selected.label} · ${selected.mass} Th` : placeholder}
        </span>
        <span aria-hidden="true">▾</span>
      </button>
      {open && (
        <div className="signal-picker-popover">
          {onCreate && (
            <button
              className="signal-picker-create"
              disabled={createDisabled}
              onClick={() => {
                close();
                onCreate();
              }}
            >
              Create from spectrum
            </button>
          )}
          <input
            ref={searchInput}
            type="search"
            aria-label="Search stored signals"
            placeholder="Search mass or label"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <div
            role="listbox"
            aria-label={listboxLabel}
            className="signal-picker-list"
          >
            {matches.length === 0 ? (
              <div className="signal-picker-empty">No matching signals</div>
            ) : (
              matches.map((option) => (
                <button
                  type="button"
                  role="option"
                  aria-selected={option.index === value}
                  key={option.index}
                  onClick={() => {
                    onChoose(option.index);
                    close();
                  }}
                >
                  {option.label} · {option.mass} Th
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
