"""Connector adapter — run Talk2View-format connectors INSIDE RadAssistant.

The connectors under connectors/ are written for Talk2View: they run out-of-process
and talk to Slicer over RPyC, and they import langchain / langgraph / pydantic /
utils.connector_base — none of which exist in Slicer's Python. RadAssistant is the
opposite: in-process, stdlib. This adapter bridges the two so their tools become
first-class RadAssistant tools, WITHOUT importing a heavy framework and WITHOUT ever
letting a broken connector take down the core:

  1. Shim the missing imports (langchain_core.tools.tool, langgraph.prebuilt.ToolNode,
     pydantic if absent, utils.connector_base, and lazy stubs for requests/rpyc) so a
     connector module can import at all.
  2. Replace the RPyC connection with an in-process Core whose `.root.slicer_*` calls
     run directly against the real `slicer` module (generic slicer_<mod>_<attr>
     dispatch + a few explicit specials).
  3. Introspect each connector's `.tools`, turn every LangChain tool into a
     {name, description, input_schema, func}, converting its Pydantic args_schema to
     plain JSON Schema, and prefix-namespace the name (st_, ts_, …) to avoid clashes
     with native tools.
  4. Wrap every load in try/except and record failures — the core keeps working.

Tool execution still goes through the normal main-thread bridge (Phase 4); here each
LoadedTool.func just calls the connector method and returns its string.

Slicer-free by dependency injection: the caller passes the `slicer` module (real in
Slicer, a mock in tests), so this whole file is unit-testable outside Slicer.
"""

import importlib.util
import inspect
import logging
import os
import sys
import types
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

log = logging.getLogger("radassistant.connectors")

# short, stable service prefixes (research: prefix-namespacing measurably helps)
_PREFIX = {
    "SlicerTools": "st", "SlicerSampleData": "sd", "TotalSegmentator": "ts",
    "GoogleMedGemma": "medgemma", "SlicerNNInteractive": "nn",
    "SlicerIDCBrowser": "idc", "SlicerAdaptiveBrush": "brush",
    "ExampleConnector": "ex",
}


# ===========================================================================
# 1. shims for the connectors' foreign imports
# ===========================================================================

class _ShimTool:
    """Stand-in for a LangChain tool: captures func, name, description, schema."""

    def __init__(self, func, args_schema=None, return_direct=False, name=None):
        self.func = func
        self.name = name or getattr(func, "__name__", "tool")
        self.description = (inspect.getdoc(func) or "").strip()
        self.args_schema = args_schema
        self.return_direct = return_direct
        self.metadata = {}

    def invoke(self, args):
        return self.func(**(args or {}))


def _shim_tool(func=None, *, args_schema=None, return_direct=False, name=None, **_kw):
    """Mimics langchain_core.tools.tool used as tool(self.method, args_schema=...)."""
    if callable(func):
        return _ShimTool(func, args_schema, return_direct, name)

    def deco(f):
        return _ShimTool(f, args_schema, return_direct, name)
    return deco


class _ShimToolNode:
    def __init__(self, tools=None, *_, **__):
        self.tools = tools or []


class _FieldInfo:
    def __init__(self, default=..., description="", **kw):
        self.default = default
        self.description = description
        self.extra = kw


def _shim_field(default=..., **kw):
    return _FieldInfo(default=default, description=kw.pop("description", ""), **kw)


class _ShimConfigDict(dict):
    def __init__(self, **kw):
        super().__init__(**kw)


class _ShimBaseModel:
    """Minimal BaseModel that can still emit JSON schema from annotations."""

    @classmethod
    def model_json_schema(cls):
        return _schema_from_annotations(cls)

    # pydantic v1 name, for connectors that call .schema()
    schema = model_json_schema


def _lazy_module(name):
    """A module stub whose attribute access returns callables that raise on USE,
    so `import requests` at a connector's top level succeeds but actually calling
    requests.post(...) fails cleanly (caught per-tool)."""
    mod = types.ModuleType(name)

    def _raise(*_a, **_k):
        raise RuntimeError(f"'{name}' is not available in this RadAssistant "
                           f"environment (stubbed by the connector adapter)")

    class _Any:
        def __getattr__(self, _n):
            return _raise

        def __call__(self, *_a, **_k):
            return _raise()
    mod.__getattr__ = lambda _n: _raise  # type: ignore
    # common attribute forms
    for attr in ("get", "post", "put", "delete", "Session", "RequestException",
                 "connect", "timed"):
        setattr(mod, attr, _raise)
    sys.modules.setdefault(name, mod)
    return mod


_SHIMS_INSTALLED = False


def install_shims():
    """Install shim modules into sys.modules (idempotent). Real pydantic is kept if
    present; everything else is shimmed."""
    global _SHIMS_INSTALLED
    if _SHIMS_INSTALLED:
        return

    # langchain_core.tools.tool
    lc = types.ModuleType("langchain_core")
    lc_tools = types.ModuleType("langchain_core.tools")
    lc_tools.tool = _shim_tool
    lc.tools = lc_tools
    sys.modules.setdefault("langchain_core", lc)
    sys.modules.setdefault("langchain_core.tools", lc_tools)

    # langgraph.prebuilt.ToolNode
    lg = types.ModuleType("langgraph")
    lg_pre = types.ModuleType("langgraph.prebuilt")
    lg_pre.ToolNode = _ShimToolNode
    lg.prebuilt = lg_pre
    sys.modules.setdefault("langgraph", lg)
    sys.modules.setdefault("langgraph.prebuilt", lg_pre)

    # pydantic — keep the real one if importable, else shim
    try:
        import pydantic  # noqa: F401
    except Exception:
        pyd = types.ModuleType("pydantic")
        pyd.BaseModel = _ShimBaseModel
        pyd.Field = _shim_field
        pyd.ConfigDict = _ShimConfigDict
        pyd.field_validator = lambda *a, **k: (lambda f: f)
        sys.modules["pydantic"] = pyd

    # utils.connector_base (absent from the repo)
    utils = types.ModuleType("utils")
    cb = types.ModuleType("utils.connector_base")

    def log_and_return_error(exc, message=None):
        log.warning("connector error: %s", exc)
        return message or f"Error: {exc}"

    class ConnectorBase:                       # connectors may subclass this
        REQUIRED_PACKAGES: list = []

        def __init__(self, rpyc_conn):
            self.talk2view_core = rpyc_conn

    cb.log_and_return_error = log_and_return_error
    cb.ConnectorBase = ConnectorBase
    utils.connector_base = cb
    sys.modules.setdefault("utils", utils)
    sys.modules.setdefault("utils.connector_base", cb)

    # lazy stubs for heavy/network deps so top-level imports don't kill loading
    for name in ("requests", "rpyc"):
        try:
            __import__(name)
        except Exception:
            _lazy_module(name)

    _SHIMS_INSTALLED = True


# ===========================================================================
# 2. Pydantic / annotation -> JSON Schema
# ===========================================================================

_PY_JSON = {str: "string", int: "integer", float: "number", bool: "boolean",
            list: "array", dict: "object"}


def _py_to_json(t):
    if t in _PY_JSON:
        return _PY_JSON[t]
    origin = getattr(t, "__origin__", None)
    if origin in (list, tuple):
        return "array"
    if origin is dict:
        return "object"
    return "string"


def _schema_from_annotations(model):
    """Build a flat JSON schema from a class's annotations + Field defaults
    (the fallback path for the pydantic shim)."""
    props, required = {}, []
    for fname, ftype in getattr(model, "__annotations__", {}).items():
        prop = {"type": _py_to_json(ftype)}
        default = getattr(model, fname, inspect._empty)
        if isinstance(default, _FieldInfo):
            if default.description:
                prop["description"] = default.description
            if default.default is ...:
                required.append(fname)
        elif default is inspect._empty:
            required.append(fname)
        props[fname] = prop
    return {"type": "object", "properties": props, "required": required}


def _normalize_schema(js):
    """Reduce a pydantic-generated schema to the flat form RadAssistant sends."""
    props = {}
    for pname, pdef in (js.get("properties") or {}).items():
        clean = {k: v for k, v in pdef.items()
                 if k in ("type", "description", "enum", "items", "default")}
        clean.setdefault("type", "string")
        props[pname] = clean
    return {"type": "object", "properties": props,
            "required": list(js.get("required", []))}


def input_schema_for(args_schema) -> dict:
    """Convert a connector tool's args_schema (pydantic model or shim) to JSON schema."""
    if args_schema is None:
        return {"type": "object", "properties": {}}
    for meth in ("model_json_schema", "schema"):
        fn = getattr(args_schema, meth, None)
        if callable(fn):
            try:
                return _normalize_schema(fn())
            except Exception as exc:                       # noqa: BLE001
                log.debug("schema extraction via %s failed: %s", meth, exc)
    return _schema_from_annotations(args_schema)


# ===========================================================================
# 3. in-process replacement for the RPyC connection
# ===========================================================================

class _NullCtx:
    def __call__(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Root:
    """Exposes the slicer_* service API the connectors expect, in-process."""

    def __init__(self, slicer_mod):
        self._slicer = slicer_mod

    def slicer_eval(self, expr):
        return eval(expr, {"slicer": self._slicer})       # noqa: S307 (trusted expr)

    def load_connector_helpers(self, _name):
        return True                                        # helpers resolve in-process

    def slicer_util_forceRenderAllViews(self):
        fn = getattr(getattr(self._slicer, "util", None), "forceRenderAllViews", None)
        return fn() if callable(fn) else None

    def slicer_util_RenderBlocker(self):
        return getattr(getattr(self._slicer, "util", None), "RenderBlocker", _NullCtx())

    def get_data_probe_info(self):
        return {}

    def __getattr__(self, name):
        # generic slicer_<mod>_<attr>  ->  getattr(getattr(slicer, mod), attr)
        if name.startswith("slicer_"):
            parts = name.split("_")
            if len(parts) >= 3:
                mod, attr = parts[1], "_".join(parts[2:])
                base = getattr(self._slicer, mod)
                return getattr(base, attr)
        raise AttributeError(name)


class InProcessCore:
    """Drop-in for the RPyC `rpyc_conn` the connectors receive."""

    def __init__(self, slicer_mod):
        self.root = _Root(slicer_mod)


# ===========================================================================
# 4. the adapter
# ===========================================================================

@dataclass
class LoadedTool:
    name: str                       # namespaced, e.g. "st_show_segmentation_3d"
    raw_name: str                   # original method name
    connector: str
    description: str
    input_schema: dict
    func: Callable                  # (**kwargs) -> str
    stream_to_user: bool = False


def _prefix_for(connector_name):
    return _PREFIX.get(connector_name, connector_name.lower()[:6])


def _import_connector(dir_path, name):
    """Import connectors/<name>/<name>.py as an isolated module."""
    py = os.path.join(dir_path, name + ".py")
    spec = importlib.util.spec_from_file_location(f"_ra_connector_{name}", py)
    module = importlib.util.module_from_spec(spec)
    # let the connector import sibling files (e.g. slicer_helpers) if it wants
    sys.path.insert(0, dir_path)
    try:
        spec.loader.exec_module(module)
    finally:
        if sys.path and sys.path[0] == dir_path:
            sys.path.pop(0)
    return module


class ConnectorAdapter:
    def __init__(self, connectors_dir, slicer_mod):
        self.connectors_dir = connectors_dir
        self.slicer = slicer_mod
        self.errors: Dict[str, str] = {}          # connector -> failure reason
        self.loaded: List[str] = []

    def available(self) -> List[str]:
        """Names of connector dirs that look valid (dir/<name>.py exists)."""
        out = []
        if not os.path.isdir(self.connectors_dir):
            return out
        for entry in sorted(os.listdir(self.connectors_dir)):
            d = os.path.join(self.connectors_dir, entry)
            if os.path.isfile(os.path.join(d, entry + ".py")):
                out.append(entry)
        return out

    def load(self, enabled=None) -> List[LoadedTool]:
        """Load tools from the enabled connectors (default: none). Never raises —
        per-connector failures are recorded in self.errors."""
        install_shims()
        core = InProcessCore(self.slicer)
        tools: List[LoadedTool] = []
        self.errors.clear()
        self.loaded.clear()

        want = set(enabled) if enabled is not None else set()
        for name in self.available():
            if enabled is not None and name not in want:
                continue
            try:
                tools += self._load_one(name, core)
                self.loaded.append(name)
            except Exception as exc:                       # noqa: BLE001
                self.errors[name] = f"{type(exc).__name__}: {exc}"
                log.warning("connector %s failed to load: %s", name, exc)
        return tools

    def _load_one(self, name, core) -> List[LoadedTool]:
        module = _import_connector(os.path.join(self.connectors_dir, name), name)
        cls = getattr(module, name, None)
        if cls is None:
            raise AttributeError(f"class {name} not found in {name}.py")
        instance = cls(core)
        raw_tools = getattr(instance, "tools", None)
        if not raw_tools:
            raise ValueError("connector exposes no .tools")

        prefix = _prefix_for(name)
        out = []
        for t in raw_tools:
            raw_name = getattr(t, "name", None) or getattr(t.func, "__name__", "tool")
            schema = input_schema_for(getattr(t, "args_schema", None))
            desc = getattr(t, "description", "") or f"{name}.{raw_name}"
            meta = getattr(t, "metadata", {}) or {}
            out.append(LoadedTool(
                name=f"{prefix}_{raw_name}",
                raw_name=raw_name,
                connector=name,
                description=desc,
                input_schema=schema,
                func=_bind(t),
                stream_to_user=bool(meta.get("stream_to_user")),
            ))
        return out


def _bind(shim_tool):
    """Return a plain callable(**kwargs) -> str for a connector tool, catching
    exceptions so a connector bug never propagates into the agent loop."""
    def call(**kwargs):
        try:
            result = shim_tool.invoke(kwargs)
            return result if isinstance(result, str) else str(result)
        except Exception as exc:                           # noqa: BLE001
            return f"Error: {shim_tool.name} failed: {exc}"
    return call


# ===========================================================================
# 5. progressive tool disclosure
# ===========================================================================

class ToolView:
    """Given the full tool catalog, expose only the subset the router selected —
    the research-backed fix for the '84 tools destroys accuracy' problem. Always
    keeps a small always-on core so the model is never stranded."""

    def __init__(self, all_defs, always_on=None):
        # all_defs: list of tool definition dicts with a "name" key
        self._by_name = {d["name"]: d for d in all_defs}
        self.always_on = list(always_on or [])

    def select(self, names, limit=12):
        """Return definitions for `names` ∪ always_on, de-duped, capped at `limit`."""
        chosen, seen = [], set()
        for n in list(self.always_on) + list(names or []):
            if n in self._by_name and n not in seen:
                seen.add(n)
                chosen.append(self._by_name[n])
            if len(chosen) >= limit:
                break
        return chosen

    def catalog(self):
        """(name, description) pairs for the router prompt — cheap, no schemas."""
        return [(d["name"], (d.get("description", "")[:120])) for d in self._by_name.values()]
