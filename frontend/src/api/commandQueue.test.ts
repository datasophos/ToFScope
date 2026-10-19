import { test, expect } from "vitest";
import { CommandQueue } from "./commandQueue";
test("network retry retains request ID and serialized revisions", async () => {
  const ids: string[] = [];
  let revision = 0,
    fail = true;
  const q = new CommandQueue(async (_id, envelope) => {
    ids.push(envelope.request_id);
    if (fail) {
      fail = false;
      throw new TypeError("lost response");
    }
    revision++;
    return { id: "a", dataset: { generation: "g" }, revision };
  });
  const a = { id: "a", revision: 0, dataset: { generation: "g" } };
  const first = await q.send(a, { type: "set_depth", depth: { mode: "all" } });
  expect(ids[0]).toBe(ids[1]);
  expect(first.revision).toBe(1);
});
