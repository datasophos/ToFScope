import type { Command, Envelope } from "./client";
type StateRef = {
  id: string;
  revision: number;
  dataset: { generation: string };
};
export class CommandQueue<T extends StateRef> {
  private chains = new Map<string, Promise<unknown>>();
  private latest = new Map<string, T>();
  constructor(
    private transport: (id: string, envelope: Envelope) => Promise<T>,
  ) {}
  observe(state: T) {
    const current = this.latest.get(state.id);
    if (!current || state.revision >= current.revision)
      this.latest.set(state.id, state);
  }
  send(state: T, command: Command): Promise<T> {
    this.observe(state);
    const next = (this.chains.get(state.id) || Promise.resolve())
      .catch(() => {})
      .then(async () => {
        const current = this.latest.get(state.id)!;
        const envelope: Envelope = {
          request_id: crypto.randomUUID(),
          expected_revision: current.revision,
          dataset_generation: current.dataset.generation,
          command,
        };
        let result: T;
        try {
          result = await this.transport(state.id, envelope);
        } catch (e) {
          if (!(e instanceof TypeError)) throw e;
          result = await this.transport(state.id, envelope);
        }
        this.observe(result);
        return result;
      });
    this.chains.set(state.id, next);
    return next;
  }
}
