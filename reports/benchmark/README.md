# Benchmark results: every secret in this folder is fake

The keys, tokens, passwords, wallets and SSH keys in these files (`tokens.json`, `report.json`, captured
request bodies under `bodies/`, logs) are **bait**. Burner makes up a fresh set at random for every scan
([`burner/node/bait.py`](../../burner/node/bait.py)) and plants it in the throwaway VM, so it can tell when a repo
reads or sends a secret.

- None of them belongs to a real account. For example, the "Stripe key" is `sk_live_` + 24 random characters.
  It looks like a real key on purpose, but Stripe never issued it.
- They're kept here on purpose, because they're the proof: the value Burner planted is the same one the malware
  sent out.
- There's nothing to revoke. If a secret scanner or a kind reader flags one of them, thank you, and it's safe to
  close as a test value.

If you find a secret anywhere in this repo that is **not** in `reports/benchmark/` or `samples/` and doesn't
match a pattern in `bait.py`, please open an issue.
