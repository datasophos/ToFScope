import type { components } from "./generated";
export type Signal = components["schemas"]["SignalSnapshot"];
export type Analysis = components["schemas"]["AnalysisSnapshot"];
export type Command = components["schemas"]["CommandEnvelope"]["command"];
export type Envelope = components["schemas"]["CommandEnvelope"];
export type Data = components["schemas"]["ExploreData"];
export type Panel = components["schemas"]["Panel"];
export type Job = components["schemas"]["JobSnapshot"];
export type JobInput = components["schemas"]["SubmitJob"];
export type Session = components["schemas"]["SessionInfo"];
let csrf = "";
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}
export async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch("/api/v1" + path, {
    credentials: "same-origin",
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrf,
      ...init.headers,
    },
  });
  if (!response.ok) {
    const err = await response
      .json()
      .catch(() => ({ code: "network", message: "Service unavailable." }));
    throw new ApiError(response.status, err.code, err.message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
export const post = <T>(path: string, value?: unknown) =>
  request<T>(path, {
    method: "POST",
    body: value === undefined ? undefined : JSON.stringify(value),
  });
export async function authenticate(): Promise<Session> {
  const fragment = location.hash;
  history.replaceState(null, "", location.pathname + location.search);
  let result: Session;
  try {
    result = fragment.startsWith("#bootstrap=")
      ? await post<Session>("/auth/bootstrap", {
          secret: decodeURIComponent(fragment.slice(11)),
        })
      : await request<Session>("/auth/session");
  } catch (e) {
    if (
      fragment.startsWith("#bootstrap=") &&
      e instanceof ApiError &&
      e.status === 401
    )
      result = await request<Session>("/auth/session");
    else throw e;
  }
  csrf = result.csrf;
  return result;
}
export async function download(aid: string, format: "csv" | "json") {
  const r = await fetch(`/api/v1/analyses/${aid}/exports/${format}`, {
    credentials: "same-origin",
  });
  if (!r.ok) throw new Error((await r.json()).message);
  const url = URL.createObjectURL(await r.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = `tofscope-${aid}.${format}`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
