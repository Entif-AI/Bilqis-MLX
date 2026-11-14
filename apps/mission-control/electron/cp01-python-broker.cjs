"use strict";

const { spawn } = require("node:child_process");
const path = require("node:path");
const readline = require("node:readline");

class Cp01PythonBroker {
  constructor({
    pythonExecutable = "python3",
    cwd = path.resolve(__dirname, "../../.."),
    env = process.env,
    requestTimeoutMs = 3000,
  } = {}) {
    this.pythonExecutable = pythonExecutable;
    this.cwd = cwd;
    this.env = env;
    this.requestTimeoutMs = requestTimeoutMs;
    this.process = null;
    this.pending = new Map();
    this.nextId = 1;
    this.eventProcesses = new Set();
  }

  connect() {
    return this.#request("connect");
  }

  status() {
    return this.#request("status");
  }

  query(request) {
    return this.#request("query", request);
  }

  disconnect() {
    return this.#request("disconnect");
  }

  subscribe(listener) {
    if (typeof listener !== "function") {
      throw new TypeError("BAMF_GUI03_EVENT_LISTENER_REQUIRED");
    }
    const child = spawn(
      this.pythonExecutable,
      ["-B", "-m", "bilqis_mlx.mission_control.electron.bridge", "--events"],
      {
        cwd: this.cwd,
        env: { ...this.env, PYTHONUNBUFFERED: "1" },
        shell: false,
        stdio: ["ignore", "pipe", "pipe"],
      },
    );
    const lines = readline.createInterface({ input: child.stdout });
    lines.on("line", (line) => {
      try {
        const payload = JSON.parse(line);
        if (payload && typeof payload === "object" && !Array.isArray(payload)) {
          listener(payload);
        }
      } catch (_error) {
        // Malformed private-broker output is dropped before the renderer boundary.
      }
    });
    child.stderr.resume();
    this.eventProcesses.add(child);
    const cleanup = () => {
      lines.close();
      this.eventProcesses.delete(child);
    };
    child.once("exit", cleanup);
    child.once("error", cleanup);
    let active = true;
    return () => {
      if (!active) return;
      active = false;
      cleanup();
      if (child.exitCode === null) child.kill();
    };
  }

  close() {
    for (const child of this.eventProcesses) {
      if (child.exitCode === null) child.kill();
    }
    this.eventProcesses.clear();
    const process = this.process;
    this.process = null;
    if (process && process.exitCode === null) {
      process.stdin.end();
      process.kill();
    }
    this.#rejectAll();
  }

  #ensureProcess() {
    if (this.process && this.process.exitCode === null) {
      return this.process;
    }
    const child = spawn(
      this.pythonExecutable,
      ["-B", "-m", "bilqis_mlx.mission_control.electron.bridge"],
      {
        cwd: this.cwd,
        env: { ...this.env, PYTHONUNBUFFERED: "1" },
        shell: false,
        stdio: ["pipe", "pipe", "pipe"],
      },
    );
    const lines = readline.createInterface({ input: child.stdout });
    lines.on("line", (line) => this.#handleLine(line));
    child.stderr.resume();
    child.once("exit", () => {
      if (this.process === child) {
        this.process = null;
      }
      this.#rejectAll();
    });
    child.once("error", () => this.#rejectAll());
    this.process = child;
    return child;
  }

  #request(op, query) {
    const child = this.#ensureProcess();
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        if (!this.pending.delete(id)) return;
        reject(this.#unavailable());
      }, this.requestTimeoutMs);
      timeout.unref?.();
      this.pending.set(id, {
        resolve: (value) => {
          clearTimeout(timeout);
          resolve(value);
        },
        reject: (error) => {
          clearTimeout(timeout);
          reject(error);
        },
      });
      const payload = query === undefined ? { id, op } : { id, op, query };
      child.stdin.write(`${JSON.stringify(payload)}\n`, (error) => {
        if (!error) return;
        this.pending.delete(id);
        reject(this.#unavailable());
      });
    });
  }

  #handleLine(line) {
    let payload;
    try {
      payload = JSON.parse(line);
    } catch (_error) {
      this.#rejectAll();
      return;
    }
    const pending = this.pending.get(payload?.id);
    if (!pending) return;
    this.pending.delete(payload.id);
    if (payload.ok === true) {
      pending.resolve(payload.result);
    } else {
      pending.reject(this.#unavailable());
    }
  }

  #rejectAll() {
    for (const { reject } of this.pending.values()) {
      reject(this.#unavailable());
    }
    this.pending.clear();
  }

  #unavailable() {
    const error = new Error("BAMF_GUI20_CP01_UNAVAILABLE");
    error.code = "BAMF_GUI20_CP01_UNAVAILABLE";
    return error;
  }
}

module.exports = { Cp01PythonBroker };
