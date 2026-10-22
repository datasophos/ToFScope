import {
  useLayoutEffect,
  useRef,
  useState,
  type InputHTMLAttributes,
} from "react";
import { formatNumber } from "../shared/numbers";
type Props = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "type" | "value" | "onChange" | "onFocus" | "onBlur"
> & {
  label: string;
  value: string;
  onChange: (value: string) => void;
  onFocus?: () => void;
  decimals?: number;
};
/** Compact while reading, exact while editing; formatting never updates the stored value. */
export function PreciseNumberInput({
  label,
  value,
  onChange,
  onFocus,
  decimals = 4,
  ...props
}: Props) {
  const [focused, setFocused] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  useLayoutEffect(() => {
    if (focused) input.current?.select();
  }, [focused]);
  const compact =
    value.trim() && Number.isFinite(Number(value))
      ? formatNumber(Number(value), decimals)
      : value;
  return (
    <input
      {...props}
      ref={input}
      type="number"
      step={props.step ?? "any"}
      aria-label={label}
      title={props.title ?? `Exact value: ${value}`}
      value={focused ? value : compact}
      onFocus={() => {
        setFocused(true);
        onFocus?.();
      }}
      onBlur={() => setFocused(false)}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}
