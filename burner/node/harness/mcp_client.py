#!/usr/bin/env python3
"""Act as an AI app's MCP client against a server under test (runs INSIDE the sandbox).

  mcp_client.py [--rounds N] -- <shell command that starts the server on stdio>

Starts the server, then does what Claude Desktop / Cursor do: initialize, tools/list (+ prompts and resources), and
calls every tool N times with plausible arguments. Some malicious servers stay clean until a tool is actually
called, or until the Nth call (Deadbugz, Aug 2026: clean for the first two calls). Prints one summary line,
"BURNER_MCP {json}", with the server's tool descriptions so the rules can look for tool poisoning.
Exit 0 if the server answered initialize, 3 if it never spoke MCP.
"""
import json
import os
import queue
import signal
import subprocess
import sys
import threading
import time

PER_REQUEST = 10


def sample_value(name, schema):
    schema = schema if isinstance(schema, dict) else {}
    if schema.get("enum"):
        return schema["enum"][0]
    if "default" in schema:
        return schema["default"]
    t = schema.get("type")
    t = t[0] if isinstance(t, list) and t else t
    n = (name or "").lower()
    if t in ("integer", "number"):
        return 1
    if t == "boolean":
        return False
    if t == "array":
        return []
    if t == "object":
        return {k: sample_value(k, v) for k, v in (schema.get("properties") or {}).items()}
    if "url" in n or "uri" in n:
        return "https://example.com"
    if "path" in n or "file" in n or "dir" in n:
        return "README.md"
    if any(w in n for w in ("city", "location", "place", "region")):
        return "London"
    if "query" in n or "search" in n or "q" == n:
        return "hello"
    return "test"


def tool_args(tool):
    schema = tool.get("inputSchema") or {}
    return {k: sample_value(k, v) for k, v in (schema.get("properties") or {}).items()}


def main():
    argv = sys.argv[1:]
    rounds = 4
    if argv[:1] == ["--rounds"]:
        rounds, argv = int(argv[1]), argv[2:]
    if argv[:1] == ["--"]:
        argv = argv[1:]
    cmd = " ".join(argv)
    posix = os.name != "nt"     # the sandbox is Linux; Windows only when the tests run on a dev machine
    proc = subprocess.Popen(["bash", "-lc", cmd] if posix else cmd, shell=not posix, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=sys.stderr, text=True, bufsize=1, start_new_session=posix)
    inbox = queue.Queue()

    def reader():
        for line in proc.stdout:
            line = line.strip()
            if line.startswith("{"):
                try:
                    inbox.put(json.loads(line))
                except ValueError:
                    pass
        inbox.put(None)

    threading.Thread(target=reader, daemon=True).start()
    ids = iter(range(1, 10 ** 6))
    summary = {"command": cmd, "initialized": False, "server": None, "tools": [], "prompts": [], "resources": [],
               "calls": 0, "call_errors": 0, "rounds": rounds}

    def send(msg):
        try:
            proc.stdin.write(json.dumps(msg) + "\n")
            proc.stdin.flush()
            return True
        except (BrokenPipeError, OSError):
            return False

    def request(method, params=None):
        rid = next(ids)
        if not send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}):
            return None
        end = time.time() + PER_REQUEST
        while time.time() < end:
            try:
                m = inbox.get(timeout=max(0.05, end - time.time()))
            except queue.Empty:
                break
            if m is None:
                return None
            if m.get("id") == rid:
                return m
            if "method" in m and "id" in m:      # server -> client request (e.g. roots/list): answer politely
                send({"jsonrpc": "2.0", "id": m["id"], "result": {}})
        return None

    try:
        r = request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {"roots": {}},
                                   "clientInfo": {"name": "claude-ai", "version": "0.14.10"}})
        if r and "result" in r:
            summary["initialized"] = True
            summary["server"] = (r["result"] or {}).get("serverInfo")
            send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            tools, cursor = [], None
            for _ in range(5):
                lr = request("tools/list", {"cursor": cursor} if cursor else {})
                res = (lr or {}).get("result") or {}
                tools += [t for t in res.get("tools") or [] if isinstance(t, dict)]
                cursor = res.get("nextCursor")
                if not cursor:
                    break
            summary["tools"] = [{"name": str(t.get("name"))[:200], "description": str(t.get("description") or "")[:4000],
                                 "params": sorted((t.get("inputSchema") or {}).get("properties") or {})[:30]}
                                for t in tools[:50]]
            for kind in ("prompts", "resources"):
                lr = request(f"{kind}/list")
                items = ((lr or {}).get("result") or {}).get(kind) or []
                summary[kind] = [{"name": str(i.get("name"))[:200], "description": str(i.get("description") or "")[:2000]}
                                 for i in items[:30] if isinstance(i, dict)]
            for _ in range(rounds):
                for t in tools[:50]:
                    cr = request("tools/call", {"name": t.get("name"), "arguments": tool_args(t)})
                    summary["calls"] += 1
                    if not cr or "error" in cr or ((cr.get("result") or {}).get("isError")):
                        summary["call_errors"] += 1
            time.sleep(3)      # payloads that fire just after a call
    finally:
        print("BURNER_MCP " + json.dumps(summary), flush=True)
        try:
            if hasattr(os, "killpg"):
                os.killpg(proc.pid, signal.SIGKILL)
            else:      # Windows (tests only): kill the shell and the server it started
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
        except OSError:
            pass
    sys.exit(0 if summary["initialized"] else 3)


if __name__ == "__main__":
    main()
