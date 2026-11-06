#!/usr/bin/env node
// Install-and-open for a VS Code extension, without VS Code (runs INSIDE the sandbox).
//
//   node vscode_host.js EXTENSION_DIR
//
// Loads the extension's "main" with a stand-in `vscode` module and calls activate(context), the way the editor does
// on startup ("*" / onStartupFinished) or on first use. GlassWorm-style sleeper extensions (Open VSX, 2026) do nothing
// until activation, then fetch a second stage, read wallets and secrets, and install themselves into every other
// IDE they find. Prints "BURNER_VSCODE {json}". Exit 0 if activate() was called.
"use strict";
const fs = require("fs"), os = require("os"), path = require("path"), Module = require("module");

const dir = path.resolve(process.argv[2] || ".");
const pkg = JSON.parse(fs.readFileSync(path.join(dir, "package.json"), "utf8"));
const summary = { id: `${pkg.publisher || "?"}.${pkg.name || "?"}`, version: pkg.version || null, main: pkg.main || null,
  activationEvents: (pkg.activationEvents || []).slice(0, 20), activated: false, error: null, commands: [] };

// ---- a permissive stand-in for the vscode API: every property exists, every call returns something usable
function deep(name) {
  const fn = function () {};
  return new Proxy(fn, {
    get(t, p) {
      if (p === "then") return undefined;                    // awaiting it resolves immediately
      if (p === Symbol.toPrimitive) return () => "";
      if (p === Symbol.iterator) return function* () {};
      if (p === "dispose") return () => {};
      if (p === "toString") return () => String(name);
      return deep(`${name}.${String(p)}`);
    },
    apply() { return deep(`${name}()`); },
    construct() { return deep(`new ${name}`); },
  });
}
const disposable = { dispose() {} };
class EventEmitter { constructor() { this.l = []; this.event = (f) => (this.l.push(f), disposable); }
  fire(e) { this.l.forEach((f) => { try { f(e); } catch (x) {} }); } dispose() {} }
class Disposable { constructor(f) { this.f = f; } dispose() { try { this.f && this.f(); } catch (e) {} }
  static from() { return disposable; } }
const Uri = { file: (p) => ({ fsPath: p, path: p, scheme: "file", toString: () => "file://" + p }),
  parse: (s) => ({ fsPath: s, path: s, scheme: "https", toString: () => s }),
  joinPath: (u, ...p) => Uri.file(path.join(u.fsPath || "", ...p)) };
const home = os.homedir(), ws = path.join(home, "projects", "workspace");
const memento = () => { const m = new Map(); return { get: (k, d) => (m.has(k) ? m.get(k) : d), update: async (k, v) => { m.set(k, v); },
  keys: () => [...m.keys()], setKeysForSync() {} }; };
const api = new Proxy({
  version: "1.95.3", EventEmitter, Disposable, Uri,
  env: { appName: "Visual Studio Code", appRoot: "/usr/share/code/resources/app", language: "en", machineId: "a1b2c3",
    sessionId: "s-1", uriScheme: "vscode", shell: "/bin/bash", remoteName: undefined, clipboard: deep("env.clipboard"),
    openExternal: async () => true, asExternalUri: async (u) => u },
  workspace: new Proxy({ workspaceFolders: [{ uri: Uri.file(ws), name: "workspace", index: 0 }], rootPath: ws,
    getConfiguration: () => ({ get: (k, d) => d, has: () => false, update: async () => {}, inspect: () => undefined }),
    onDidChangeConfiguration: () => disposable, onDidSaveTextDocument: () => disposable, onDidOpenTextDocument: () => disposable,
    findFiles: async () => [], textDocuments: [], fs: deep("workspace.fs") }, { get: (t, p) => (p in t ? t[p] : deep(`workspace.${String(p)}`)) }),
  commands: new Proxy({ registerCommand: (id) => (summary.commands.push(id), disposable), executeCommand: async () => undefined,
    getCommands: async () => [] }, { get: (t, p) => (p in t ? t[p] : deep(`commands.${String(p)}`)) }),
  window: new Proxy({ showInformationMessage: async () => undefined, showWarningMessage: async () => undefined,
    showErrorMessage: async () => undefined, createOutputChannel: () => deep("OutputChannel"),
    createStatusBarItem: () => deep("StatusBarItem"), activeTextEditor: undefined, visibleTextEditors: [] },
    { get: (t, p) => (p in t ? t[p] : deep(`window.${String(p)}`)) }),
  extensions: { all: [], getExtension: () => undefined, onDidChange: () => disposable },
}, { get: (t, p) => (p in t ? t[p] : deep(`vscode.${String(p)}`)) });

const origResolve = Module._resolveFilename;
Module._resolveFilename = function (request, ...rest) {
  if (request === "vscode") return "vscode";
  return origResolve.call(this, request, ...rest);
};
require.cache.vscode = { id: "vscode", filename: "vscode", loaded: true, exports: api };

const storage = path.join(home, ".config", "Code", "User", "globalStorage", summary.id);
const context = { subscriptions: [], extensionPath: dir, extensionUri: Uri.file(dir), extensionMode: 1,
  globalState: memento(), workspaceState: memento(), storagePath: path.join(storage, "ws"), globalStoragePath: storage,
  storageUri: Uri.file(path.join(storage, "ws")), globalStorageUri: Uri.file(storage), logUri: Uri.file(path.join(storage, "logs")),
  logPath: path.join(storage, "logs"), asAbsolutePath: (p) => path.join(dir, p),
  secrets: { get: async () => undefined, store: async () => {}, delete: async () => {}, onDidChange: () => disposable },
  environmentVariableCollection: deep("environmentVariableCollection"), extension: { id: summary.id, packageJSON: pkg },
  languageModelAccessInformation: deep("lm") };

function done(code) {
  console.log("BURNER_VSCODE " + JSON.stringify(summary));
  process.exit(code);
}
process.on("uncaughtException", (e) => { summary.error = summary.error || `uncaught: ${String(e && e.message || e).slice(0, 200)}`; });
process.on("unhandledRejection", (e) => { summary.error = summary.error || `rejection: ${String(e && e.message || e).slice(0, 200)}`; });

(async () => {
  try {
    const main = pkg.main ? path.resolve(dir, pkg.main) : null;
    if (!main) { summary.error = "no \"main\" in package.json (a theme or language pack: no code runs)"; return done(4); }
    const ext = require(main);
    if (typeof ext.activate === "function") {
      await ext.activate(context);
      summary.activated = true;
    } else {
      summary.error = "main has no activate()";
    }
  } catch (e) {
    summary.error = `${e && e.name}: ${String(e && e.message || e).slice(0, 200)}`;
  }
  // an editor stays open: give delayed payloads time, then report
  setTimeout(() => done(summary.activated ? 0 : 4), Number(process.env.BURNER_VSCODE_WAIT || 20000));
})();
