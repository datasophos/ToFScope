import { useEffect, useRef, useState, useCallback } from "react";
import {
  request,
  ApiError,
  post,
  type Analysis,
  type Data,
  type Command,
} from "../api/client";
import { CommandQueue } from "../api/commandQueue";
export function useAnalysis(initial: Analysis) {
  const [state, setState] = useState(initial),
    [data, setData] = useState<Data | null>(null),
    [error, setError] = useState("");
  const [pendingPanels, setPendingPanels] = useState(new Set<string>());
  const [panelStates, setPanelStates] = useState<Record<string, Analysis>>({});
  const current = useRef(initial),
    mounted = useRef(true),
    loading = useRef(false),
    dataRef = useRef<Data | null>(null),
    prepared = useRef<Analysis | null>(null);
  const queue = useRef(
    new CommandQueue<Analysis>((id, e) => post(`/analyses/${id}/commands`, e)),
  );
  const accept = useCallback((a: Analysis) => {
    if (
      !mounted.current ||
      a.id !== current.current.id ||
      a.revision < current.current.revision
    )
      return;
    if (JSON.stringify(a) === JSON.stringify(current.current)) return;
    current.current = a;
    queue.current.observe(a);
    setState(a);
  }, []);
  const refresh = useCallback(async () => {
    if (loading.current) return;
    loading.current = true;
    try {
      const a = await request<Analysis>(`/analyses/${initial.id}`);
      accept(a);
      if (dataRef.current?.revision === a.revision) return;
      const before = prepared.current;
      const parts: string[] = [];
      if (!before || before.dataset.generation !== a.dataset.generation)
        parts.push("spectrum", "ion", "front", "profile");
      else {
        const different = (x: unknown, y: unknown) =>
          JSON.stringify(x) !== JSON.stringify(y);
        const image = (v: Analysis) =>
          v.signals.find((s) => s.id === v.image_signal_id);
        const active = different(image(before), image(a)),
          geometry =
            different(before.depth_anchors, a.depth_anchors) ||
            before.depth_unit !== a.depth_unit ||
            before.depth_coordinates !== a.depth_coordinates;
        if (
          active ||
          different(before.depth, a.depth) ||
          before.display.colormap !== a.display.colormap ||
          before.display.log !== a.display.log ||
          before.display.image !== a.display.image
        )
          parts.push("ion");
        if (
          active ||
          geometry ||
          different(before.roi.slice(2), a.roi.slice(2)) ||
          before.display.colormap !== a.display.colormap ||
          before.display.log !== a.display.log
        )
          parts.push("front");
        if (
          active ||
          geometry ||
          different(before.roi, a.roi) ||
          different(
            before.signals.filter((s) =>
              before.profile_signal_ids.includes(s.id),
            ),
            a.signals.filter((s) => a.profile_signal_ids.includes(s.id)),
          ) ||
          before.display.relative !== a.display.relative
        )
          parts.push("profile");
      }
      if (parts.length) setPendingPanels(new Set(parts));
      const d = parts.length
        ? await request<Data>(
            `/analyses/${a.id}/data?panels=${parts.join(",")}`,
          )
        : {
            analysis_id: a.id,
            revision: a.revision,
            dataset_generation: a.dataset.generation,
            panels: {},
          };
      if (
        mounted.current &&
        d.dataset_generation === current.current.dataset.generation &&
        d.revision === a.revision &&
        d.revision === current.current.revision
      ) {
        const merged = {
          ...d,
          panels: { ...dataRef.current?.panels, ...d.panels },
        };
        dataRef.current = merged;
        prepared.current = a;
        setData(merged);
        setPanelStates((old) => ({
          ...old,
          ...Object.fromEntries(Object.keys(d.panels).map((key) => [key, a])),
        }));
        setPendingPanels(new Set());
        setError("");
      }
    } catch (e) {
      if (mounted.current) setError((e as Error).message);
    } finally {
      loading.current = false;
    }
  }, [initial.id, accept]);
  useEffect(() => {
    mounted.current = true;
    let view: string | undefined,
      disposed = false;
    let attaching = false;
    const attach = async () => {
      if (attaching || disposed) return;
      attaching = true;
      try {
        const v = await post<{ id: string }>(`/analyses/${initial.id}/views`);
        if (disposed)
          void request(`/views/${v.id}`, { method: "DELETE" }).catch(() => {});
        else view = v.id;
      } catch (e) {
        if (!disposed) setError((e as Error).message);
      } finally {
        attaching = false;
      }
    };
    void attach();
    void refresh();
    const poll = setInterval(() => void refresh(), 1000),
      heartbeat = setInterval(() => {
        if (!view) {
          void attach();
          return;
        }
        void post(`/views/${view}/heartbeat`).catch((e) => {
          if (disposed) return;
          if (e instanceof ApiError && e.status === 404) {
            view = undefined;
            void attach();
          } else setError(e.message);
        });
      }, 15000);
    return () => {
      disposed = true;
      mounted.current = false;
      clearInterval(poll);
      clearInterval(heartbeat);
      if (view)
        void request(`/views/${view}`, { method: "DELETE" }).catch(() => {});
    };
  }, [initial.id, refresh]);
  const send = async (command: Command) => {
    try {
      setError("");
      const a = await queue.current.send(current.current, command);
      accept(a);
      await refresh();
      return a;
    } catch (e) {
      setError((e as Error).message);
      await refresh();
      throw e;
    }
  };
  return {
    state,
    data,
    error,
    send,
    refresh,
    accept,
    setError,
    pendingPanels,
    panelStates,
  };
}
