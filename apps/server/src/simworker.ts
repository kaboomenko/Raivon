// Pool of headless Godot processes running game/server/sim_worker.gd (docs/dev/server.md):
// the server reuses the client's GDScript rules instead of a second implementation.
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";

const GAME_DIR = fileURLToPath(new URL("../../../game", import.meta.url));

type Pending = { resolve: (v: Record<string, unknown>) => void; reject: (e: Error) => void; timer: NodeJS.Timeout };

class Worker {
  private proc: ChildProcessWithoutNullStreams;
  private pending = new Map<number, Pending>();
  private nextId = 1;
  alive = true;

  constructor(bin: string) {
    this.proc = spawn(bin, ["--headless", "--path", GAME_DIR, "--script", "res://server/sim_worker.gd"], { stdio: "pipe" });
    createInterface({ input: this.proc.stdout }).on("line", (line) => {
      if (!line.startsWith("@@")) return; // engine log lines
      const msg = JSON.parse(line.slice(2)) as Record<string, unknown>;
      const id = Number(msg.id);
      const p = this.pending.get(id);
      if (!p) return;
      clearTimeout(p.timer);
      this.pending.delete(id);
      p.resolve(msg);
    });
    this.proc.on("exit", () => {
      this.alive = false;
      for (const p of this.pending.values()) p.reject(new Error("sim worker exited"));
      this.pending.clear();
    });
  }

  get load() {
    return this.pending.size;
  }

  call(cmd: string, args: Record<string, unknown>, timeoutMs: number): Promise<Record<string, unknown>> {
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`sim worker timeout: ${cmd}`));
      }, timeoutMs);
      this.pending.set(id, { resolve, reject, timer });
      this.proc.stdin.write(JSON.stringify({ id, cmd, ...args }) + "\n");
    });
  }

  stop() {
    if (this.alive) this.proc.stdin.write("quit\n");
  }
}

export class SimPool {
  private workers: Worker[] = [];

  constructor(private bin = process.env.GODOT_BIN ?? "/opt/godot/Godot_v4.5.1-stable_linux.x86_64", size = 2) {
    for (let i = 0; i < size; i++) this.workers.push(new Worker(this.bin));
  }

  /** Sends a command to the least busy live worker (restarting dead ones). */
  async call(cmd: string, args: Record<string, unknown> = {}, timeoutMs = 15000) {
    this.workers = this.workers.map((w) => (w.alive ? w : new Worker(this.bin)));
    const w = this.workers.reduce((a, b) => (b.load < a.load ? b : a));
    return w.call(cmd, args, timeoutMs);
  }

  close() {
    for (const w of this.workers) w.stop();
  }
}
