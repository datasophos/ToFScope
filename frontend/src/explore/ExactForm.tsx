import { useEffect, useState } from "react";
export function ExactForm({
  labels,
  values,
  onApply,
  button,
}: {
  labels: string[];
  values: number[];
  onApply: (values: number[]) => void;
  button: string;
}) {
  const [draft, setDraft] = useState(values.map(String));
  useEffect(() => setDraft(values.map(String)), [values.join(",")]);
  return (
    <form
      className="exact-form"
      onSubmit={(e) => {
        e.preventDefault();
        onApply(draft.map(Number));
      }}
    >
      {labels.map((label, i) => (
        <label key={label}>
          {label}
          <input
            type="number"
            step="1"
            required
            aria-label={label}
            value={draft[i]}
            onChange={(e) =>
              setDraft((s) => s.map((v, j) => (j === i ? e.target.value : v)))
            }
          />
        </label>
      ))}
      <button>{button}</button>
    </form>
  );
}
