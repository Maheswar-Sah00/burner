#!/usr/bin/env python3
"""Load a model repo the way people load untrusted models (runs INSIDE the sandbox).

  load_model.py MODEL_DIR

1. Pickle weights (.bin .pt .pth .ckpt .pkl .pickle .joblib), the way torch.load(weights_only=False), older PyTorch
   (< 2.6), Lightning checkpoints, pickle.load and joblib.load do: every global the file names is really imported
   and called. That is how a malicious pickle runs code. Libraries that aren't installed here (torch, numpy,
   sklearn...) are replaced by inert stand-ins, so a normal model loads into placeholders and does nothing.
2. Custom code named in config.json / tokenizer_config.json "auto_map", imported and instantiated the way
   transformers does with trust_remote_code=True (and, through 2026's bypass bugs, sometimes without it).
safetensors files are only listed: that format can't carry code.
Prints "BURNER_MODEL {json}". Exit 0 if anything was loaded.
"""
import importlib
import importlib.abc
import importlib.util
import json
import os
import pickle
import sys
import types
import zipfile

PICKLE_EXT = (".bin", ".pt", ".pth", ".ckpt", ".pkl", ".pickle", ".joblib")
STUB_ROOTS = {"torch", "transformers", "numpy", "safetensors", "tokenizers", "accelerate", "einops", "sklearn",
              "huggingface_hub", "sentencepiece", "flash_attn", "triton", "scipy", "pandas", "joblib",
              "lightning", "pytorch_lightning", "torchvision", "timm", "diffusers", "peft", "bitsandbytes"}
MAX_FILE = 400 * 1024 * 1024


class Stub:
    """Inert stand-in for any class or function of a library that isn't installed."""
    def __init__(self, *a, **k):
        pass

    def __call__(self, *a, **k):
        return Stub()

    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return Stub()

    def __setstate__(self, state):
        pass

    def __iter__(self):
        return iter(())

    def __getitem__(self, k):
        return Stub()

    def __setitem__(self, k, v):
        pass


_stub_classes = {}


def stub_class(qualname):
    if qualname not in _stub_classes:
        _stub_classes[qualname] = type(qualname.rsplit(".", 1)[-1], (Stub,), {"__module__": qualname.rsplit(".", 1)[0]})
    return _stub_classes[qualname]


class StubModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return stub_class(f"{self.__name__}.{name}")


class StubFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """`import torch` / `from transformers import PreTrainedModel` succeed with stand-ins when not installed."""
    def find_spec(self, fullname, path, target=None):
        if fullname.split(".")[0] not in STUB_ROOTS:
            return None
        for finder in sys.meta_path:
            if finder is self or not hasattr(finder, "find_spec"):
                continue
            try:
                if finder.find_spec(fullname, path, target):
                    return None      # really installed: use it
            except Exception:
                pass
        return importlib.util.spec_from_loader(fullname, self, is_package=True)

    def create_module(self, spec):
        m = StubModule(spec.name)
        m.__path__ = []
        return m

    def exec_module(self, module):
        pass


class UntrustedUnpickler(pickle.Unpickler):
    """pickle.Unpickler with torch.load(weights_only=False) semantics: globals are imported for real."""
    def find_class(self, module, name):
        if module.split(".")[0] in STUB_ROOTS:     # tensors/arrays: placeholders, whether or not torch is installed
            return stub_class(f"{module}.{name}")
        try:
            return super().find_class(module, name)
        except (ImportError, AttributeError):
            return stub_class(f"{module}.{name}")

    def persistent_load(self, pid):      # torch tensor storages
        return Stub()


def unpickle_all(f, limit=8):
    n = 0
    while n < limit:
        try:
            UntrustedUnpickler(f).load()
            n += 1
        except EOFError:
            break
    return n


def load_weights(path, log):
    size = os.path.getsize(path)
    if size > MAX_FILE:
        log["skipped"].append({"file": path, "why": f"{size // 2**20} MB, over the limit"})
        return
    try:
        if zipfile.is_zipfile(path):       # torch >= 1.6 format: <archive>/data.pkl + tensor blobs
            with zipfile.ZipFile(path) as z:
                pkls = [n for n in z.namelist() if n.endswith(".pkl")]
                for n in pkls[:4]:
                    with z.open(n) as f:
                        unpickle_all(f, limit=1)
                log["loaded"].append({"file": path, "format": "torch zip", "pickles": pkls[:4]})
        else:                              # legacy torch / plain pickle / joblib: a run of pickles
            with open(path, "rb") as f:
                n = unpickle_all(f)
            log["loaded"].append({"file": path, "format": "pickle", "objects": n})
    except Exception as e:
        log["errors"].append({"file": path, "error": f"{type(e).__name__}: {str(e)[:200]}"})


def import_custom_code(model_dir, log):
    refs = set()
    for cfg in ("config.json", "tokenizer_config.json", "preprocessor_config.json"):
        try:
            data = json.load(open(os.path.join(model_dir, cfg)))
        except (OSError, ValueError):
            continue
        for v in (data.get("auto_map") or {}).values():
            for ref in (v if isinstance(v, list) else [v]):
                if isinstance(ref, str) and ref:
                    refs.add(ref.split("--")[-1])     # "other/repo--module.Class" -> "module.Class"
    if not refs:
        return
    pkg = types.ModuleType("hf_remote_code")
    pkg.__path__ = [os.path.abspath(model_dir)]
    sys.modules["hf_remote_code"] = pkg
    for ref in sorted(refs):
        mod, _, cls = ref.rpartition(".")
        try:
            m = importlib.import_module(f"hf_remote_code.{mod}")
            obj = getattr(m, cls, None)
            if isinstance(obj, type):
                try:
                    obj(Stub())                      # from_pretrained builds the class with its config
                except Exception as e:
                    log["errors"].append({"code": ref, "error": f"init: {type(e).__name__}: {str(e)[:160]}"})
            log["code"].append(ref)
        except Exception as e:
            log["errors"].append({"code": ref, "error": f"{type(e).__name__}: {str(e)[:200]}"})


def main():
    model_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    sys.meta_path.insert(0, StubFinder())
    log = {"loaded": [], "code": [], "skipped": [], "errors": [], "safetensors": []}
    for root, dirs, files in os.walk(model_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules"]
        for fn in sorted(files):
            p = os.path.join(root, fn)
            if fn.endswith(".safetensors"):
                log["safetensors"].append(p)
            elif fn.endswith(PICKLE_EXT):
                load_weights(p, log)
    import_custom_code(model_dir, log)
    print("BURNER_MODEL " + json.dumps(log, default=str), flush=True)
    sys.exit(0 if log["loaded"] or log["code"] else 4)


if __name__ == "__main__":
    main()
