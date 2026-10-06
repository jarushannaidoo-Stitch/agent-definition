#!/usr/bin/env python3
"""Onboard model bindings for the agent definition pack.

Discovers available models for a registered harness (harnesses/<name>.yaml),
prompts for main + each capability (or accepts --set / --answers), and writes
profiles/<profile>.yaml (default: personal) without touching shipping profiles
such as profiles/codex.yaml or profiles/claude.yaml.

Usage:
  ./adapters/onboard-models.sh --list-harnesses
  ./adapters/onboard-models.sh --harness codex --list-models [--json]
  ./adapters/onboard-models.sh --harness claude --dry-run
  ./adapters/onboard-models.sh --harness codex --set main=gpt-6.1-sol:high:fast \\
      --set orchestrator=gpt-6.1-sol:high:fast --export
  ./adapters/onboard-models.sh --harness codex --answers answers.yaml --export
  ./adapters/onboard-models.sh --harness example   # any registered harness

Agent flow (skills/onboard-models): --list-models --json, ask_user for each
slot, write an answers file, then --answers FILE --export (no TTY required).
Default profile name is personal-<harness> so harnesses never overwrite each other.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys

# Reuse pack constants / YAML subset from the shared adapter lib.
_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import agentpack as ap  # noqa: E402

SLOTS = ("main",) + ap.CAPABILITIES
REASONING_FALLBACK = ("low", "medium", "high", "xhigh", "max", "ultra")
SERVICE_TIERS = ("fast",)  # pack vocabulary; omit for harness default
INHERIT = ap.INHERIT_MODEL


# ---------------------------------------------------------------------------
# Harness registry
# ---------------------------------------------------------------------------

def load_harness(root: pathlib.Path, name: str) -> dict:
    harnesses = ap.load_harness_registry(root)
    if name not in harnesses:
        known = ", ".join(sorted(harnesses)) or "none"
        raise ap.PackError(f"unknown harness {name!r}; registered: {known} "
                           f"(copy harnesses/_template.yaml to add one)")
    return harnesses[name]


def expand_home(path: str) -> pathlib.Path:
    return pathlib.Path(os.path.expanduser(path))


# ---------------------------------------------------------------------------
# Model discovery
# ---------------------------------------------------------------------------

class ModelInfo:
    __slots__ = ("id", "name", "efforts", "source", "service_tiers")

    def __init__(self, id: str, name: str = "", efforts=None, source: str = "",
                 service_tiers=None):
        self.id = id
        self.name = name or id
        self.efforts = list(REASONING_FALLBACK) if efforts is None else list(efforts)
        self.source = source
        self.service_tiers = list(SERVICE_TIERS) if service_tiers is None else list(service_tiers)


def discover_models(root: pathlib.Path, harness: dict) -> tuple[list[ModelInfo], list[str]]:
    """Return (models, notes). Always allows free-text even when empty."""
    models: list[ModelInfo] = []
    notes: list[str] = []
    seen: set[str] = set()

    def add(m: ModelInfo):
        if m.id in seen:
            return
        seen.add(m.id)
        models.append(m)

    for step in harness.get("model_discovery") or []:
        if not isinstance(step, dict):
            continue
        kind = step.get("kind")
        try:
            if kind == "static":
                for raw in step.get("models") or []:
                    if isinstance(raw, dict) and raw.get("id"):
                        add(ModelInfo(raw["id"], raw.get("name") or raw["id"],
                                      raw.get("efforts"), "static",
                                      raw.get("service_tiers")))
                    elif isinstance(raw, str):
                        add(ModelInfo(raw, source="static"))
            elif kind == "inherit":
                add(ModelInfo(INHERIT, "Harness chooses (parent / agent settings)",
                              [], "inherit", []))
                notes.append(f"{INHERIT}: the harness picks the model; pack cannot pin it.")
            elif kind == "codex_cache":
                for m in _from_codex_cache():
                    add(m)
            elif kind == "claude_catalog":
                for m in _from_claude_catalog():
                    add(m)
            elif kind == "pstack_mdc":
                for m in _from_pstack(step.get("path") or ".cursor/rules/pstack-models.mdc"):
                    add(m)
            elif kind == "command_json":
                for m in _from_command_json(step):
                    add(m)
            elif kind == "pi_models_json":
                for m in _from_pi_models_json():
                    add(m)
            elif kind == "hermes_config":
                for m in _from_hermes_config():
                    add(m)
            else:
                notes.append(f"skipped unknown discovery kind {kind!r}")
        except Exception as exc:  # noqa: BLE001 - best-effort discovery
            notes.append(f"{kind} discovery failed: {exc}")

    # Seed suggestions from the shipping profile when discovery is thin.
    shipping = (harness.get("profile") or {}).get("shipping")
    if shipping:
        for m in _from_shipping_profile(root, shipping, harness["name"]):
            add(m)

    if not models:
        notes.append("No models discovered; type any model id (warning shown).")
    return models, notes


def _from_codex_cache() -> list[ModelInfo]:
    path = pathlib.Path.home() / ".codex" / "models_cache.json"
    if not path.is_file():
        raise FileNotFoundError(path)
    data = json.loads(path.read_text())
    out = []
    for raw in data.get("models") or []:
        slug = raw.get("slug")
        if not slug:
            continue
        efforts = [e.get("effort") for e in (raw.get("supported_reasoning_levels") or [])
                   if isinstance(e, dict) and e.get("effort")]
        # Pack vocabulary uses service_tier: fast (maps to Codex priority + fast_mode).
        tiers = []
        if raw.get("additional_speed_tiers") or raw.get("service_tiers"):
            tiers = ["fast"]
        out.append(ModelInfo(slug, raw.get("display_name") or slug, efforts or None,
                             f"codex:{path.name}", tiers))
    return out


def _from_claude_catalog() -> list[ModelInfo]:
    root = pathlib.Path.home() / ".claude" / "cache" / "model-catalog"
    if not root.is_dir():
        raise FileNotFoundError(root)
    files = sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise FileNotFoundError("empty model-catalog")
    data = json.loads(files[0].read_text())
    models = (((data.get("catalog") or {}).get("config") or {}).get("models")) or []
    out = []
    for raw in models:
        mid = raw.get("id")
        if not mid:
            continue
        thinking = raw.get("thinking") or {}
        efforts = [e.get("id") for e in (thinking.get("effort_options") or [])
                   if isinstance(e, dict) and e.get("id")]
        tiers = ["fast"] if raw.get("fast_mode") else []
        out.append(ModelInfo(mid, raw.get("name") or mid, efforts or None,
                             f"claude:{files[0].name}", tiers))
    return out


def _from_pstack(rel: str) -> list[ModelInfo]:
    path = expand_home(rel if rel.startswith("~") or rel.startswith("/") else f"~/{rel}")
    if not path.is_file():
        raise FileNotFoundError(path)
    ids: list[str] = []
    lines = path.read_text().splitlines()
    # Skip YAML frontmatter (description:, alwaysApply: true, globs: ...).
    if lines and lines[0].strip() == "---":
        for idx in range(1, len(lines)):
            if lines[idx].strip() == "---":
                lines = lines[idx + 1:]
                break
    for line in lines:
        if ":" not in line or line.strip().startswith("#"):
            continue
        _, _, rhs = line.partition(":")
        for part in rhs.split(","):
            tok = part.strip()
            if tok and tok not in ("inherit-parent", "auto", "true", "false") and re.match(r"^[\w./:-]+$", tok):
                ids.append(tok)
    # Preserve order, unique
    seen = set()
    out = []
    for i in ids:
        if i in seen:
            continue
        seen.add(i)
        out.append(ModelInfo(i, source=f"pstack:{path.name}"))
    return out


def _from_command_json(step: dict) -> list[ModelInfo]:
    cmd = list(step.get("command") or [])
    if not cmd:
        raise ValueError("command_json needs command")
    cmd = [c.replace("{HOME}", str(pathlib.Path.home())) for c in cmd]
    # Prefer the real binary when `codex` is aliased in the interactive shell.
    if cmd[0] == "codex":
        for candidate in (
            pathlib.Path.home() / ".local/share/mise/installs/node/24.3.0/bin/codex",
            pathlib.Path("/usr/local/bin/codex"),
        ):
            if candidate.is_file():
                cmd[0] = str(candidate)
                break
        else:
            cmd[0] = "codex"
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"exit {proc.returncode}")
    text = proc.stdout.strip()
    start = min((i for i in (text.find("{"), text.find("[")) if i >= 0), default=-1)
    if start < 0:
        raise RuntimeError("no JSON in command output")
    data = json.loads(text[start:])
    path = step.get("json_path") or ""
    cur = data
    for part in path.split(".") if path else []:
        if part:
            cur = cur[part]
    id_key = step.get("id_key") or "id"
    name_key = step.get("name_key") or "name"
    efforts_path = step.get("efforts_path")
    effort_id_key = step.get("effort_id_key") or "effort"
    out = []
    for raw in cur or []:
        if not isinstance(raw, dict):
            continue
        mid = raw.get(id_key)
        if not mid:
            continue
        efforts = None
        if efforts_path:
            levels = raw.get(efforts_path) or []
            efforts = [e.get(effort_id_key) for e in levels
                       if isinstance(e, dict) and e.get(effort_id_key)]
        out.append(ModelInfo(mid, raw.get(name_key) or mid, efforts, "command_json"))
    return out



def _from_pi_models_json() -> list[ModelInfo]:
    """Read ~/.pi/agent/models.json and settings.json when Pi is installed."""
    agent_dir = pathlib.Path(
        os.environ.get("PI_CODING_AGENT_DIR", str(pathlib.Path.home() / ".pi" / "agent"))
    ).expanduser()
    out: list[ModelInfo] = []
    settings = agent_dir / "settings.json"
    if settings.is_file():
        data = json.loads(settings.read_text())
        default = data.get("defaultModel") or data.get("default_model")
        if isinstance(default, str) and default:
            effort = data.get("defaultThinkingLevel") or data.get("default_thinking_level")
            efforts = [effort] if isinstance(effort, str) else None
            out.append(ModelInfo(default, f"Pi default ({default})", efforts, "pi:settings.json"))
    models_path = agent_dir / "models.json"
    if models_path.is_file():
        data = json.loads(models_path.read_text())
        providers = data.get("providers") or {}
        if isinstance(providers, dict):
            for pname, pdata in providers.items():
                if not isinstance(pdata, dict):
                    continue
                for raw in pdata.get("models") or []:
                    if isinstance(raw, str):
                        mid = f"{pname}/{raw}" if "/" not in raw else raw
                        out.append(ModelInfo(mid, mid, None, "pi:models.json"))
                    elif isinstance(raw, dict) and raw.get("id"):
                        mid = raw["id"]
                        if "/" not in mid:
                            mid = f"{pname}/{mid}"
                        out.append(ModelInfo(mid, raw.get("name") or mid, None, "pi:models.json"))
        for raw in data.get("models") or []:
            if isinstance(raw, dict) and raw.get("id"):
                out.append(ModelInfo(raw["id"], raw.get("name") or raw["id"], None, "pi:models.json"))
            elif isinstance(raw, str):
                out.append(ModelInfo(raw, source="pi:models.json"))
    if not out:
        raise FileNotFoundError(f"no Pi models under {agent_dir} (install Pi or use static suggestions)")
    return out


def _from_hermes_config() -> list[ModelInfo]:
    """Read ~/.hermes config for a default model when Hermes is installed."""
    import shutil
    home = pathlib.Path.home() / ".hermes"
    candidates = [home / "config.yaml", home / "config.yml", home / "config.json"]
    profiles = home / "profiles"
    if profiles.is_dir():
        for p in profiles.iterdir():
            if p.is_dir():
                candidates.extend([p / "config.yaml", p / "config.yml", p / "config.json"])
    out: list[ModelInfo] = []
    for path in candidates:
        if not path.is_file():
            continue
        raw_text = path.read_text()
        if path.suffix == ".json":
            data = json.loads(raw_text)
        else:
            try:
                data = ap.parse_yaml_nested(raw_text, str(path))
            except ap.PackError:
                for line in raw_text.splitlines():
                    s = line.strip()
                    if s.startswith("model:") or s.startswith("default_model:"):
                        _, _, v = s.partition(":")
                        v = v.strip().strip('"').strip("'")
                        if v:
                            out.append(ModelInfo(v, v, None, f"hermes:{path.name}"))
                continue
        model = data.get("model") or data.get("default_model")
        if isinstance(model, str) and model:
            out.append(ModelInfo(model, model, None, f"hermes:{path.name}"))
        elif isinstance(model, dict):
            for key in ("default", "id", "name", "model"):
                if isinstance(model.get(key), str) and model[key]:
                    out.append(ModelInfo(model[key], model[key], None, f"hermes:{path.name}"))
                    break
        providers = data.get("providers")
        if isinstance(providers, dict):
            for pname, pdata in providers.items():
                if isinstance(pdata, dict) and isinstance(pdata.get("default"), str):
                    mid = pdata["default"]
                    if "/" not in mid:
                        mid = f"{pname}/{mid}"
                    out.append(ModelInfo(mid, mid, None, f"hermes:{path.name}"))
    if not out:
        raise FileNotFoundError("no Hermes config under ~/.hermes (install Hermes or use static suggestions)")
    return out


def _from_shipping_profile(root: pathlib.Path, name: str, harness: str) -> list[ModelInfo]:
    path = root / "profiles" / f"{name}.yaml"
    if not path.is_file():
        return []
    try:
        profile = ap.load_profile(root, name, harness)
    except ap.PackError:
        return []
    ids = []
    if profile.main:
        ids.append(profile.main.model)
    for b in profile.capabilities.values():
        ids.append(b.model)
    out = []
    seen = set()
    for i in ids:
        if i in seen:
            continue
        seen.add(i)
        out.append(ModelInfo(i, source=f"profile:{name}"))
    return out


# ---------------------------------------------------------------------------
# Binding I/O
# ---------------------------------------------------------------------------

def parse_binding_spec(spec: str) -> dict:
    """model[:reasoning[:service_tier]] - trailing empties mean omit."""
    parts = spec.split(":")
    if not parts or not parts[0].strip():
        raise ap.PackError(f"empty binding spec {spec!r}")
    out = {"model": parts[0].strip()}
    if len(parts) > 1 and parts[1].strip():
        out["reasoning"] = parts[1].strip()
    if len(parts) > 2 and parts[2].strip():
        out["service_tier"] = parts[2].strip()
    return out


def load_answers(path: pathlib.Path) -> dict:
    text = path.read_text()
    if path.suffix.lower() == ".json" or text.lstrip().startswith("{"):
        data = json.loads(text)
    else:
        data = ap.parse_yaml_nested(text, str(path))
    if not isinstance(data, dict):
        raise ap.PackError(f"{path}: expected a mapping")
    return data


def seed_bindings(root: pathlib.Path, harness: dict, profile_name: str) -> dict:
    """Prefer existing personal profile, else shipping profile, else empty."""
    out: dict = {"main": None, "capabilities": {}}
    for candidate in (profile_name, (harness.get("profile") or {}).get("shipping")):
        if not candidate:
            continue
        path = root / "profiles" / f"{candidate}.yaml"
        if not path.is_file():
            continue
        try:
            # Harness on the file must match; personal for another harness is skipped.
            prof = ap.load_profile(root, candidate, harness["name"])
        except ap.PackError:
            continue
        if prof.main:
            out["main"] = {
                "model": prof.main.model,
                **({} if not prof.main.reasoning else {"reasoning": prof.main.reasoning}),
                **({} if not prof.main.service_tier else {"service_tier": prof.main.service_tier}),
            }
        for cap, b in prof.capabilities.items():
            out["capabilities"][cap] = {
                "model": b.model,
                **({} if not b.reasoning else {"reasoning": b.reasoning}),
                **({} if not b.service_tier else {"service_tier": b.service_tier}),
            }
        break
    return out


def apply_sets(bindings: dict, sets: list[str]) -> None:
    for item in sets:
        if "=" not in item:
            raise ap.PackError(f"--set expects SLOT=model[:reasoning[:tier]], got {item!r}")
        slot, _, spec = item.partition("=")
        slot = slot.strip()
        binding = parse_binding_spec(spec)
        if slot == "main":
            bindings["main"] = binding
        elif slot in ap.CAPABILITIES:
            bindings.setdefault("capabilities", {})[slot] = binding
        else:
            raise ap.PackError(f"unknown slot {slot!r}; expected main or one of {', '.join(ap.CAPABILITIES)}")


def apply_answers(bindings: dict, answers: dict) -> None:
    if "main" in answers and answers["main"] is not None:
        bindings["main"] = dict(answers["main"])
    caps = answers.get("capabilities") or {}
    if not isinstance(caps, dict):
        raise ap.PackError("answers.capabilities must be a mapping")
    for cap, raw in caps.items():
        if cap not in ap.CAPABILITIES:
            raise ap.PackError(f"unknown capability {cap!r} in answers")
        bindings.setdefault("capabilities", {})[cap] = dict(raw)


def complete_bindings(bindings: dict, models: list[ModelInfo], allow_missing: bool = False) -> None:
    """Fill missing slots from the first discovered model or require them."""
    by_id = {m.id: m for m in models}
    caps = bindings.setdefault("capabilities", {})
    for slot in SLOTS:
        cur = bindings.get("main") if slot == "main" else caps.get(slot)
        if cur and cur.get("model"):
            mid = cur["model"]
            if mid not in by_id and mid != INHERIT:
                print(f"warning: {slot} model {mid!r} was not in the discovered list "
                      f"(accepted as free-text)", file=sys.stderr)
            continue
        if allow_missing:
            continue
        if not models:
            raise ap.PackError(f"no binding for {slot} and no models to default from; "
                               f"pass --set {slot}=model:effort or --answers")
        # Default: first model (often shipping suggestion).
        m = models[0]
        effort = m.efforts[2] if len(m.efforts) > 2 else (m.efforts[-1] if m.efforts else None)
        # Prefer medium when present.
        if "medium" in m.efforts:
            effort = "medium"
        if "high" in m.efforts and slot in ("main", "orchestrator", "adversarial_audit", "taste", "verify"):
            effort = "high"
        binding = {"model": m.id}
        if effort:
            binding["reasoning"] = effort
        if m.service_tiers and "fast" in m.service_tiers and slot != "fast_narrow":
            # Only auto-add fast for Codex-like packs when the model supports it;
            # Claude shipping omits it. Leave unset unless seed already had it.
            pass
        if slot == "main":
            bindings["main"] = binding
        else:
            caps[slot] = binding


def render_profile_yaml(profile_name: str, harness: dict, bindings: dict,
                        description: str | None = None, strict: bool = True) -> str:
    hname = harness["name"]
    display = harness.get("display_name") or hname
    desc = description or (
        f"Personal model choices for {display}. "
        f"Shipping defaults stay in profiles/{(harness.get('profile') or {}).get('shipping') or hname}.yaml. "
        f"Activate with {(harness.get('profile') or {}).get('env') or (hname.upper() + '_PROFILE')}={profile_name}."
    )
    lines = [
        f"# Personal model binding profile {profile_name!r} for harness {hname}.",
        f"# Generated by adapters/onboard-models.sh. Do not hand-edit shipping profiles.",
        f"profile: {profile_name}",
        f"harness: {hname}",
        f'description: "{desc}"',
        f"strict: {'true' if strict else 'false'}",
        "",
    ]
    main = bindings.get("main")
    if main and main.get("model"):
        lines.append("main:")
        lines.append(f"  model: {main['model']}")
        if main.get("reasoning"):
            lines.append(f"  reasoning: {main['reasoning']}")
        if main.get("service_tier"):
            lines.append(f"  service_tier: {main['service_tier']}")
        lines.append("")
    lines.append("capabilities:")
    caps = bindings.get("capabilities") or {}
    for cap in ap.CAPABILITIES:
        b = caps.get(cap)
        if not b or not b.get("model"):
            raise ap.PackError(f"missing binding for capability {cap}")
        lines.append(f"  {cap}:")
        lines.append(f"    model: {b['model']}")
        if b.get("reasoning"):
            lines.append(f"    reasoning: {b['reasoning']}")
        if b.get("service_tier"):
            lines.append(f"    service_tier: {b['service_tier']}")
    lines.append("")
    lines.append("roles: {}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Interactive prompts
# ---------------------------------------------------------------------------

def interactive_fill(bindings: dict, models: list[ModelInfo], notes: list[str]) -> None:
    if not sys.stdin.isatty():
        raise ap.PackError("no TTY for interactive onboarding; pass --set or --answers "
                           "(see skills/onboard-models for the agent flow)")
    print("Model onboarding")
    if notes:
        for n in notes:
            print(f"  note: {n}")
    print("Available models:")
    for i, m in enumerate(models, 1):
        efforts = ",".join(m.efforts) if m.efforts else "-"
        tiers = ",".join(m.service_tiers) if m.service_tiers else "-"
        print(f"  {i:2}. {m.id:<32} {m.name}  [efforts={efforts} tiers={tiers}] ({m.source})")
    print("  Enter a number, a model id, or blank to keep the current value.")
    print("  For inherit-parent hosts, type: inherit-parent")
    by_id = {m.id: m for m in models}

    def pick(slot: str, current: dict | None) -> dict:
        cur = current or {}
        cur_s = ""
        if cur.get("model"):
            cur_s = cur["model"]
            if cur.get("reasoning"):
                cur_s += ":" + cur["reasoning"]
            if cur.get("service_tier"):
                cur_s += ":" + cur["service_tier"]
        print(f"\n{slot} [{cur_s or 'unset'}]")
        raw = input("  model> ").strip()
        if not raw:
            if cur.get("model"):
                model_id = cur["model"]
            elif models:
                model_id = models[0].id
            else:
                raise ap.PackError(f"{slot}: need a model id")
        elif raw.isdigit() and 1 <= int(raw) <= len(models):
            model_id = models[int(raw) - 1].id
        else:
            model_id = raw
            if model_id not in by_id and model_id != INHERIT:
                print(f"  warning: {model_id!r} not in discovered list (free-text accepted)")
        info = by_id.get(model_id)
        efforts = info.efforts if info else list(REASONING_FALLBACK)
        tiers = info.service_tiers if info else list(SERVICE_TIERS)
        default_effort = cur.get("reasoning") or (
            "high" if "high" in efforts else (efforts[0] if efforts else "")
        )
        effort_raw = input(f"  reasoning [{default_effort or 'omit'}]> ").strip()
        effort = effort_raw if effort_raw else default_effort
        if effort and efforts and effort not in efforts and model_id != INHERIT:
            print(f"  warning: effort {effort!r} not in {efforts} (accepted)")
        default_tier = cur.get("service_tier") or ""
        tier_hint = ",".join(tiers) if tiers else "omit"
        tier_raw = input(f"  service_tier [{default_tier or 'omit'}; known: {tier_hint}]> ").strip()
        tier = tier_raw if tier_raw else default_tier
        out = {"model": model_id}
        if effort:
            out["reasoning"] = effort
        if tier:
            out["service_tier"] = tier
        return out

    bindings["main"] = pick("main", bindings.get("main"))
    caps = bindings.setdefault("capabilities", {})
    for cap in ap.CAPABILITIES:
        caps[cap] = pick(cap, caps.get(cap))


# ---------------------------------------------------------------------------
# Export helper
# ---------------------------------------------------------------------------

def run_export(root: pathlib.Path, harness: dict, profile_name: str) -> int:
    hname = harness["name"]
    env = os.environ.copy()
    profile_env = (harness.get("profile") or {}).get("env")
    if profile_env:
        env[profile_env] = profile_name
    cmd = [sys.executable, str(_HERE / "agentpack.py"), hname]
    if hname == "cursor":
        # Cursor export is a dual skills mirror with no profile flag; the profile is recorded for later.
        print("note: cursor export does not apply model profiles yet; skills re-exported unchanged")
    else:
        cmd += ["--profile", profile_name]
    print(f"export: {' '.join(cmd)} ({profile_env}={profile_name})")
    return subprocess.call(cmd, cwd=str(root), env=env)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--harness",
                        help="registered harness name (harnesses/<name>.yaml), e.g. codex, cursor, grokbot, claude")
    parser.add_argument("--profile", default=None,
                        help="profile file stem to write (default: personal-<harness> -> profiles/personal-<harness>.yaml)")
    parser.add_argument("--list-models", action="store_true", help="print discovered models and exit")
    parser.add_argument("--list-harnesses", action="store_true",
                        help="print registered harness names (one per line) and exit; --harness not needed")
    parser.add_argument("--json", action="store_true",
                        help="with --list-models: one JSON object (harness, slots, current bindings, models, notes) for agents")
    parser.add_argument("--activate", action="store_true",
                        help="after write, make this profile the harness default (profiles/.active/<harness>) "
                             "so exporters and check.sh use it without an env var")
    parser.add_argument("--deactivate", action="store_true",
                        help="remove profiles/.active/<harness> (back to the shipping profile) and exit")
    parser.add_argument("--force", action="store_true",
                        help="allow overwriting an existing profile that is bound to a different harness")
    parser.add_argument("--dry-run", action="store_true", help="print the profile YAML; write nothing")
    parser.add_argument("--set", action="append", default=[], dest="sets",
                        help="SLOT=model[:reasoning[:service_tier]] (repeatable; non-interactive)")
    parser.add_argument("--answers", type=pathlib.Path,
                        help="YAML/JSON file with main: and capabilities: bindings")
    parser.add_argument("--from-profile", help="seed from this profile name (default: existing --profile, else shipping)")
    parser.add_argument("--export", action="store_true", help="run the harness exporter with the new profile after write")
    parser.add_argument("--strict", choices=("true", "false"), default="true")
    parser.add_argument("--description", help="override profile description string")
    parser.add_argument("--no-default-fill", action="store_true",
                        help="with --set/--answers, do not auto-fill unspecified slots from discovery")
    args = parser.parse_args(argv)

    root = pathlib.Path(os.environ.get("PACK_ROOT", _HERE.parents[1]))
    try:
        if args.list_harnesses:
            for name, h in sorted(ap.load_harness_registry(root).items()):
                print(f"{name}\t{h.get('display_name') or name}")
            return 0
        if not args.harness:
            parser.error("--harness is required (see --list-harnesses)")
        harness = load_harness(root, args.harness)
        if not args.profile:
            args.profile = f"personal-{harness['name']}"
        active_file = root / ap.ACTIVE_DIR / harness["name"]
        if args.deactivate:
            if active_file.is_file():
                active_file.unlink()
                print(f"deactivated: removed {_short(active_file)}; {harness['name']} exports use the shipping profile")
            else:
                print(f"no active pointer for {harness['name']}; already on the shipping profile")
            return 0
        models, notes = discover_models(root, harness)
        profile_env = (harness.get("profile") or {}).get("env") or harness["name"].upper() + "_PROFILE"

        if args.list_models and args.json:
            current = seed_bindings(root, harness, args.from_profile or args.profile)
            print(json.dumps({
                "pack_root": str(root),
                "harness": harness["name"],
                "display_name": harness.get("display_name") or harness["name"],
                "profile": args.profile,
                "profile_env": profile_env,
                "profile_exists": (root / "profiles" / f"{args.profile}.yaml").is_file(),
                "active_profile": ap.active_profile_name(root, harness["name"]),
                "shipping_profile": (harness.get("profile") or {}).get("shipping"),
                "exporter": f"./adapters/export-{harness['name']}.sh",
                "export_applies_profile": harness["name"] != "cursor",
                "slots": list(SLOTS),
                "main_required": harness["name"] in ap.CONCRETE_MODEL_HARNESSES,
                "inherit_model": INHERIT,
                "current": current,
                "models": [{"id": m.id, "name": m.name, "efforts": m.efforts,
                            "service_tiers": m.service_tiers, "source": m.source} for m in models],
                "notes": notes,
            }, indent=2))
            return 0

        if args.list_models:
            print(f"harness: {harness['name']} ({harness.get('display_name')})")
            for n in notes:
                print(f"note: {n}")
            for m in models:
                print(f"{m.id}\t{m.name}\tefforts={','.join(m.efforts) or '-'}\t"
                      f"tiers={','.join(m.service_tiers) or '-'}\t{m.source}")
            return 0

        # Seed order: --from-profile, else existing --profile file, else shipping.
        bindings = seed_bindings(root, harness, args.from_profile or args.profile)

        if args.answers:
            apply_answers(bindings, load_answers(args.answers))
        if args.sets:
            apply_sets(bindings, args.sets)

        # Non-interactive when the caller supplied sets/answers/from-profile (agent flow).
        interactive = not args.sets and not args.answers and not args.from_profile
        if interactive:
            interactive_fill(bindings, models, notes)
        else:
            complete_bindings(bindings, models, allow_missing=args.no_default_fill)
            # Still require every capability after fill.
            missing = [c for c in ap.CAPABILITIES
                       if not (bindings.get("capabilities") or {}).get(c, {}).get("model")]
            if missing:
                raise ap.PackError(f"missing bindings for: {', '.join(missing)}")
            if not (bindings.get("main") or {}).get("model"):
                # main is optional for skills-only inherit hosts; required for concrete-model harnesses.
                if harness["name"] in ap.CONCRETE_MODEL_HARNESSES or args.harness == "codex":
                    # Prefer fill already done; if still missing, error.
                    if not models:
                        raise ap.PackError("main binding required")
                    complete_bindings(bindings, models, allow_missing=False)

        yaml_text = render_profile_yaml(
            args.profile, harness, bindings,
            description=args.description,
            strict=(args.strict == "true"),
        )

        # Validate round-trip through the pack loader (write to a temp name mentally).
        # load_profile needs the file on disk with matching profile/harness - for dry-run,
        # parse via parse_yaml_nested shape check only.
        parsed = ap.parse_yaml_nested(yaml_text, f"profiles/{args.profile}.yaml")
        if parsed.get("profile") != args.profile or parsed.get("harness") != harness["name"]:
            raise ap.PackError("internal: rendered profile header mismatch")

        if args.dry_run:
            print(yaml_text, end="" if yaml_text.endswith("\n") else "\n")
            print(f"# dry-run: would write profiles/{args.profile}.yaml "
                  f"({(harness.get('profile') or {}).get('env') or harness['name'].upper()+'_PROFILE'}={args.profile})",
                  file=sys.stderr)
            return 0

        out = root / "profiles" / f"{args.profile}.yaml"
        if out.name.startswith("_"):
            raise ap.PackError(f"refusing to write {out.name}")
        shipping = (harness.get("profile") or {}).get("shipping")
        if shipping and args.profile == shipping:
            raise ap.PackError(
                f"refusing to overwrite shipping profile profiles/{shipping}.yaml; "
                f"use --profile personal (or another name)"
            )
        if out.is_file() and not args.force:
            existing = ap.parse_yaml_nested(out.read_text(), str(out))
            other = existing.get("harness") if isinstance(existing, dict) else None
            if other and other != harness["name"]:
                raise ap.PackError(
                    f"profiles/{args.profile}.yaml is bound to harness {other!r}, not {harness['name']!r}; "
                    f"use the default --profile personal-{harness['name']} or pass --force"
                )
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(yaml_text)
        # Confirm it loads.
        ap.load_profile(root, args.profile, harness["name"])
        print(f"wrote {_short(out)}")
        if harness["name"] == "cursor":
            print("note: profile recorded; Cursor export does not apply model profiles yet "
                  "(per-chat models come from the Cursor picker and pstack-models.mdc)")
        print(f"activate: {(harness.get('profile') or {}).get('env') or harness['name'].upper()+'_PROFILE'}={args.profile} "
              f"./adapters/export-{harness['name']}.sh   "
              f"# or: python3 adapters/lib/agentpack.py {harness['name']} --profile {args.profile}")

        if args.activate:
            active_file.parent.mkdir(parents=True, exist_ok=True)
            active_file.write_text(args.profile + "\n")
            print(f"active: {_short(active_file)} -> {args.profile} "
                  f"(undo: ./adapters/onboard-models.sh --harness {harness['name']} --deactivate)")

        if args.export:
            return run_export(root, harness, args.profile)
        return 0
    except ap.PackError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\naborted", file=sys.stderr)
        return 130


def _short(path: pathlib.Path) -> str:
    try:
        return str(path.relative_to(pathlib.Path.home()))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    sys.exit(main())
