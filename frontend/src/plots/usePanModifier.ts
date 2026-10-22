import { useEffect, useState } from "react";

/** Temporary pan mode; keep the toolbar's persistent tool selection separate. */
export function usePanModifier() {
  const [held, setHeld] = useState(false);
  useEffect(() => {
    const update = (event: KeyboardEvent | PointerEvent) =>
      setHeld(event.ctrlKey || event.metaKey);
    const clear = () => setHeld(false);
    const visibility = () => {
      if (document.hidden) clear();
    };
    window.addEventListener("keydown", update, true);
    window.addEventListener("keyup", update, true);
    window.addEventListener("pointerdown", update, true);
    window.addEventListener("pointermove", update, true);
    window.addEventListener("blur", clear);
    document.addEventListener("visibilitychange", visibility);
    return () => {
      window.removeEventListener("keydown", update, true);
      window.removeEventListener("keyup", update, true);
      window.removeEventListener("pointerdown", update, true);
      window.removeEventListener("pointermove", update, true);
      window.removeEventListener("blur", clear);
      document.removeEventListener("visibilitychange", visibility);
    };
  }, []);
  return held;
}
