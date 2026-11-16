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

test("queued display patches use the latest acknowledged display state", async () => {
  const initial = {
    id: "a",
    revision: 0,
    dataset: { generation: "g" },
    display: {
      log: true,
      relative: true,
      image: "sims" as "sims" | "se",
      front_orientation: "xz" as "xz" | "yz",
    },
  };
  let server = initial;
  const queue = new CommandQueue(async (_id, envelope) => {
    if (envelope.command.type !== "set_display")
      throw new Error("unexpected command");
    server = {
      ...server,
      revision: server.revision + 1,
      display: {
        ...server.display,
        log: envelope.command.log,
        relative: envelope.command.relative,
        image: envelope.command.image,
        front_orientation:
          envelope.command.front_orientation ??
          server.display.front_orientation,
      },
    };
    return server;
  });
  const change =
    (patch: Partial<typeof initial.display>) => (state: typeof initial) => ({
      type: "set_display" as const,
      ...state.display,
      ...patch,
    });
  const first = queue.send(initial, change({ front_orientation: "yz" }));
  const second = queue.send(initial, change({ log: false }));
  await Promise.all([first, second]);
  expect(server.display.front_orientation).toBe("yz");
  expect(server.display.log).toBe(false);
});
