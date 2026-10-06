#!/usr/bin/env python3
"""Shared adapter library and CLI for the agent definition pack.

One parser, one renderer per native format, and one plan/apply/check engine
used by every exporter. Exporters build a desired file tree, then either write
it (export), print the differences (--dry-run) or fail on drift (--check).

Usage:
  agentpack.py codex  [--check | --dry-run] [--prune] [--diff] [--only PARTS]
                      [--profile NAME] [--explain]
  agentpack.py cursor [--check | --dry-run] [--prune] [--diff]
  agentpack.py grokbot [--check | --dry-run] [--prune] [--diff]
                       [--profile NAME] [--explain]
  agentpack.py claude|pi|hermes|<registered>  same flags as grokbot (skills-only)
  agentpack.py list-harnesses [--checkable]

Model binding: agents/<id>/agent.yaml names a semantic capability only.
profiles/<name>.yaml binds capabilities (and optional per-role overrides and
the root session) to concrete models for one harness. Codex uses profile
"codex" and Grok Bot uses "grokbot" unless --profile or AGENTPACK_PROFILE
selects another. A strict profile fails closed when a role's capability is
unmapped. The model value "inherit-parent" means the harness picks the model
(the parent session or its own agent settings); only skills-only adapters
(grokbot) accept it, because Codex needs a concrete model string.

Registered harnesses live in harnesses/<name>.yaml (skip _*). Built-in
harnesses (codex, cursor, grokbot) keep special exporters; every other
registered harness uses the generic skills-only exporter (same SKILL.md
shape), writes $OUT_ENV (default ~/ + out_default), and resolves
profiles/<shipping>.yaml via $PROFILE_ENV. Copy harnesses/_template.yaml
to add pi/hermes-like hosts.

Grok Bot export is skills-only: SKILL.md folders (same frontmatter as Cursor)
in $GROKBOT_SKILLS_OUT (default ~/agents/grokbot-skills) plus a
.agentpack-resolved sidecar recording the profile resolution. Nothing is
pushed to a Grok Bot box; copy or sync that folder to the box workflows dir.

Codex parts: agents, skills, agents-md, config (default: all).

Skill bodies: "## Harness notes: <harness>" sections reach only that harness
(codex -> ~/.agents/skills, cursor -> ~/.cursor/skills, grokbot ->
~/agents/grokbot-skills); the portable copy
(~/agents/skills) keeps every section. Untargeted "## Harness notes" stays.

Tool vocabulary: adapters/tool-map.yaml maps neutral tool verbs to each
harness's tools and lists leak patterns. Every run lints skill text outside
targeted harness notes; leaks are drift unless the skill is lint.pending.
Exit codes: 0 clean or written, 1 drift found by --check, 2 error.

Environment overrides (same names as the original shell exporters):
  PACK_ROOT, CODEX_HOME, CODEX_AGENTS_OUT, AGENTS_SKILLS_OUT,
  CODEX_AGENTS_MD_OUT, CODEX_CONFIG, CURSOR_SKILLS_OUT, PORTABLE_SKILLS_OUT,
  AGENTPACK_PRUNE_DIR, AGENTPACK_PROFILE (codex), GROKBOT_PROFILE,
  GROKBOT_SKILLS_OUT.
"""
from __future__ import annotations

import argparse
import difflib
import os
import pathlib
import re
import shutil
import sys
import time
from dataclasses import dataclass, field

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    tomllib = None

SCHEMA_MAJOR = "1"
IGNORED_NAMES = {".DS_Store", "__pycache__", ".pytest_cache"}
IGNORED_SUFFIXES = (".pyc",)
SOURCE_ONLY_FILES = {"skill.yaml", "BODY.md"}
CAPABILITIES = (
    "orchestrator", "implement", "fast_narrow", "adversarial_audit", "taste", "verify",
)
AGENT_MODEL_KEYS = {"capability"}
BINDING_KEYS = {"model", "reasoning", "service_tier", "fallbacks"}
PROFILE_KEYS = {"profile", "harness", "description", "strict", "main", "capabilities", "roles", "default"}
RESOLVED_SIDECAR = ".agentpack-resolved"
# Harness names allowed in "## Harness notes: <name>[, <name>]" headings.
# Populated from harnesses/*.yaml at load_pack / load_harness_registry time;
# the tuple below is the boot fallback before a pack root is known.
KNOWN_HARNESSES = ("codex", "cursor", "grokbot", "claude", "pi", "hermes")
HARNESS_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
# Profile model value meaning "the harness chooses" (parent session / agent settings).
INHERIT_MODEL = "inherit-parent"
# Harnesses whose adapter writes concrete model strings and so reject INHERIT_MODEL.
CONCRETE_MODEL_HARNESSES = {"codex"}
HARNESS_NOTES_RE = re.compile(r"^## Harness notes:\s*(.*?)\s*$")
SECTION_END_RE = re.compile(r"^#{1,2}\s")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
TOOL_MAP_PATH = pathlib.Path("adapters") / "tool-map.yaml"
TOOL_MAP_KEYS = {"schema_version", "verbs", "leaks", "lint"}
TOOL_LINT_KEYS = {"pending", "exempt"}
VERB_RE = re.compile(r"^[a-z][a-z_]*$")
SANDBOX_MAP = {
    "read-only": "read-only",
    "workspace-write": "workspace-write",
    "full": "danger-full-access",
}


class PackError(Exception):
    pass


# ---------------------------------------------------------------------------
# Pack reading
# ---------------------------------------------------------------------------

def parse_yaml_lite(text: str, source: str = "<yaml>") -> dict:
    """Parse the small YAML subset the pack uses.

    Supported: top-level `key: value`, top-level `key:` followed by either a
    two-space indented `- item` list or a two-space indented mapping of
    scalars, and inline `[]`. Values wrapped in double quotes lose the outer
    quotes only; escapes are kept verbatim. That matches the original
    exporters byte for byte, so generated files do not change. Anything else
    raises PackError instead of being silently misread.
    """
    data: dict = {}
    block_key = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        where = f"{source}:{lineno}"
        if raw.startswith("  "):
            if block_key is None or raw.startswith("   "):
                raise PackError(f"{where}: unsupported indentation")
            container = data[block_key]
            if stripped.startswith("- "):
                if container == {}:
                    container = data[block_key] = []
                if not isinstance(container, list):
                    raise PackError(f"{where}: list item inside mapping")
                container.append(_scalar(stripped[2:].strip()))
            else:
                if container == []:
                    container = data[block_key] = {}
                if not isinstance(container, dict):
                    raise PackError(f"{where}: mapping entry inside list")
                key, sep, value = stripped.partition(":")
                if not sep:
                    raise PackError(f"{where}: expected key: value")
                container[key.strip()] = _scalar(value.strip())
            continue
        if raw[0].isspace():
            raise PackError(f"{where}: unsupported indentation")
        key, sep, value = raw.partition(":")
        if not sep:
            raise PackError(f"{where}: expected key: value")
        key, value = key.strip(), value.strip()
        if key in data:
            raise PackError(f"{where}: duplicate key {key!r}")
        if value:
            data[key] = _scalar(value)
            block_key = None
        else:
            data[key] = []  # becomes a dict on the first mapping entry
            block_key = key
    return data


def _scalar(value: str):
    if value == "[]":
        return []
    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    return value


def parse_yaml_nested(text: str, source: str = "<yaml>") -> dict:
    """Parse the nested YAML subset used by profiles/*.yaml.

    Supported: mappings nested in two-space steps, `- scalar` lists, `- key: value` mapping list items with indented keys, inline
    `[]`, `{}` and `[a, b]`, `true`/`false`, double-quoted strings and full-line
    or trailing ` #` comments on unquoted values. Anything else raises.
    """
    lines = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        where = f"{source}:{lineno}"
        if raw[indent:indent + 1] == "\t" or indent % 2:
            raise PackError(f"{where}: indentation must be multiples of two spaces")
        lines.append((indent, stripped, where))
    pos = 0

    def block(indent: int):
        nonlocal pos
        is_list = lines[pos][1].startswith("- ")
        out: list | dict = [] if is_list else {}
        while pos < len(lines):
            ind, text_, where = lines[pos]
            if ind < indent:
                break
            if ind > indent:
                raise PackError(f"{where}: unexpected indentation")
            if is_list:
                if not text_.startswith("- "):
                    raise PackError(f"{where}: mapping entry inside list")
                rest = text_[2:].strip()
                pos += 1
                # Mapping list item: "- key: value" with optional indented keys.
                if ":" in rest and not rest.startswith("[") and not rest.startswith("{"):
                    key, sep, value = rest.partition(":")
                    key, value = key.strip(), value.strip()
                    if not sep or not key:
                        raise PackError(f"{where}: expected key: value in list item")
                    item: dict = {}
                    if value and not value.startswith("#"):
                        item[key] = _nested_scalar(value, where)
                    elif pos < len(lines) and lines[pos][0] > indent:
                        item[key] = block(indent + 2)
                    else:
                        item[key] = None
                    child = indent + 2
                    while pos < len(lines) and lines[pos][0] >= child:
                        cind, ctext, cwhere = lines[pos]
                        if cind != child:
                            raise PackError(f"{cwhere}: unexpected indentation in list item")
                        if ctext.startswith("- "):
                            raise PackError(f"{cwhere}: nested list must be under a key")
                        ck, csep, cv = ctext.partition(":")
                        ck, cv = ck.strip(), cv.strip()
                        if not csep or not ck:
                            raise PackError(f"{cwhere}: expected key: value")
                        if ck in item:
                            raise PackError(f"{cwhere}: duplicate key {ck!r}")
                        pos += 1
                        if cv and not cv.startswith("#"):
                            item[ck] = _nested_scalar(cv, cwhere)
                        elif pos < len(lines) and lines[pos][0] > child:
                            item[ck] = block(child + 2)
                        else:
                            item[ck] = None
                    out.append(item)
                else:
                    out.append(_nested_scalar(rest, where))
                continue
            if text_.startswith("- "):
                raise PackError(f"{where}: list item inside mapping")
            key, sep, value = text_.partition(":")
            key, value = key.strip(), value.strip()
            if not sep or not key:
                raise PackError(f"{where}: expected key: value")
            if key in out:
                raise PackError(f"{where}: duplicate key {key!r}")
            pos += 1
            if value and not value.startswith("#"):
                out[key] = _nested_scalar(value, where)
            elif pos < len(lines) and lines[pos][0] > indent:
                out[key] = block(indent + 2)
            else:
                out[key] = None
        return out

    if not lines:
        return {}
    data = block(0)
    if not isinstance(data, dict):
        raise PackError(f"{source}: top level must be a mapping")
    return data


def _nested_scalar(value: str, where: str):
    if value.startswith('"'):
        end = value.find('"', 1)
        rest = value[end + 1:].strip() if end > 0 else None
        if end <= 0 or (rest and not rest.startswith("#")):
            raise PackError(f"{where}: bad quoted string")
        return value[1:end]
    if " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    if value == "{}":
        return {}
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [_nested_scalar(v.strip(), where) for v in inner.split(",")] if inner else []
    if value in ("true", "false"):
        return value == "true"
    if value.startswith(("[", "{")):
        raise PackError(f"{where}: unsupported inline collection {value!r}")
    return value


def _is_ignored(path: pathlib.Path) -> bool:
    return path.name in IGNORED_NAMES or path.name.endswith(IGNORED_SUFFIXES)


@dataclass
class Skill:
    id: str
    meta: dict
    body: str
    root: pathlib.Path

    def companions(self) -> dict[str, pathlib.Path]:
        """Relative path -> source file for every companion file."""
        out = {}
        for path in sorted(self.root.rglob("*")):
            rel = path.relative_to(self.root)
            if any(_is_ignored(pathlib.Path(p)) for p in rel.parts):
                continue
            if len(rel.parts) == 1 and rel.name in SOURCE_ONLY_FILES:
                continue
            if path.is_file():
                out[rel.as_posix()] = path
        return out


@dataclass
class Agent:
    id: str
    meta: dict
    instructions: str


@dataclass
class Pack:
    root: pathlib.Path
    manifest: dict
    skills: list[Skill]
    agents: list[Agent]


def load_pack(root: pathlib.Path) -> Pack:
    manifest_path = root / "manifest.yaml"
    if not manifest_path.is_file():
        raise PackError(f"no manifest.yaml under {root}")
    manifest = parse_yaml_lite(manifest_path.read_text(), str(manifest_path))
    if str(manifest.get("schema_version", "")).split(".")[0] != SCHEMA_MAJOR:
        raise PackError(f"unsupported schema_version {manifest.get('schema_version')!r}")

    skill_ids = _child_dirs(root / "skills")
    agent_ids = _child_dirs(root / "agents")
    for kind, on_disk in (("skills", skill_ids), ("agents", agent_ids)):
        listed = manifest.get(kind) or []
        if sorted(listed) != on_disk:
            raise PackError(
                f"manifest {kind} and {kind}/ folders differ: "
                f"only in manifest {sorted(set(listed) - set(on_disk))}, "
                f"only on disk {sorted(set(on_disk) - set(listed))}"
            )

    skills = []
    for sid in skill_ids:
        d = root / "skills" / sid
        meta = parse_yaml_lite((d / "skill.yaml").read_text(), str(d / "skill.yaml"))
        _require(meta, ("id", "name", "description"), d / "skill.yaml", sid)
        body = (d / "BODY.md").read_text()
        filter_harness_notes(body, None, str(d / "BODY.md"))  # validate headings
        skills.append(Skill(sid, meta, body, d))

    agents = []
    for aid in agent_ids:
        d = root / "agents" / aid
        meta = parse_yaml_lite((d / "agent.yaml").read_text(), str(d / "agent.yaml"))
        _require(meta, ("id", "name", "description", "kind", "model"), d / "agent.yaml", aid)
        model = meta["model"]
        if not isinstance(model, dict) or "capability" not in model:
            raise PackError(f"{d / 'agent.yaml'}: model.capability is required")
        extra = sorted(set(model) - AGENT_MODEL_KEYS)
        if extra:
            raise PackError(
                f"{d / 'agent.yaml'}: model.{', model.'.join(extra)} do not belong in a role; "
                "bind models in profiles/<name>.yaml (capabilities or roles)"
            )
        if model["capability"] not in CAPABILITIES:
            raise PackError(f"{d / 'agent.yaml'}: unknown capability {model['capability']!r}; "
                            f"expected one of {', '.join(CAPABILITIES)}")
        agents.append(Agent(aid, meta, (d / "INSTRUCTIONS.md").read_text()))
    return Pack(root, manifest, skills, agents)


def _child_dirs(path: pathlib.Path) -> list[str]:
    return sorted(p.name for p in path.iterdir() if p.is_dir() and not _is_ignored(p))


def _require(meta: dict, keys, path, folder_id):
    missing = [k for k in keys if k not in meta]
    if missing:
        raise PackError(f"{path}: missing {missing}")
    if meta["id"] != folder_id:
        raise PackError(f"{path}: id {meta['id']!r} does not match folder {folder_id!r}")


# ---------------------------------------------------------------------------
# Harness registry (harnesses/<name>.yaml)
# ---------------------------------------------------------------------------

def load_harness_registry(root: pathlib.Path) -> dict[str, dict]:
    """Load harnesses/*.yaml (skip _*). Sets KNOWN_HARNESSES as a side effect."""
    global KNOWN_HARNESSES
    d = root / "harnesses"
    out: dict[str, dict] = {}
    if not d.is_dir():
        KNOWN_HARNESSES = tuple(KNOWN_HARNESSES)
        return out
    for path in sorted(d.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        data = parse_yaml_nested(path.read_text(), str(path))
        name = data.get("name") or path.stem
        if not isinstance(name, str) or not HARNESS_NAME_RE.match(name):
            raise PackError(f"{_short(path)}: name must match {HARNESS_NAME_RE.pattern}")
        if name != path.stem:
            raise PackError(f"{_short(path)}: name {name!r} must match file stem {path.stem!r}")
        if name in out:
            raise PackError(f"duplicate harness {name!r}")
        skills = data.get("skills") or {}
        if not isinstance(skills, dict):
            raise PackError(f"{_short(path)}: skills must be a mapping")
        for key in ("out_env", "out_default", "shape"):
            if key not in skills:
                raise PackError(f"{_short(path)}: skills.{key} is required")
        if skills.get("shape") != "skill_md":
            raise PackError(f"{_short(path)}: only skills.shape skill_md is supported today")
        profile = data.get("profile") or {}
        if not isinstance(profile, dict):
            raise PackError(f"{_short(path)}: profile must be a mapping")
        agents = data.get("agents") or {}
        if not isinstance(agents, dict):
            raise PackError(f"{_short(path)}: agents must be a mapping")
        builtin = data.get("builtin", False)
        if not isinstance(builtin, bool):
            raise PackError(f"{_short(path)}: builtin must be true or false")
        data["name"] = name
        data["skills"] = skills
        data["profile"] = profile
        data["agents"] = agents
        data["builtin"] = builtin
        data["_path"] = path
        out[name] = data
    if out:
        KNOWN_HARNESSES = tuple(sorted(out))
    return out


def harness_skills_out(harness: dict) -> pathlib.Path:
    skills = harness["skills"]
    env = skills["out_env"]
    if os.environ.get(env):
        return pathlib.Path(os.environ[env]).expanduser()
    default = skills["out_default"]
    p = pathlib.Path(default).expanduser()
    if not p.is_absolute():
        p = pathlib.Path.home() / default
    return p


def checkable_harness_names(root: pathlib.Path) -> list[str]:
    """Harnesses check.sh should run: always codex+cursor; others when out dir exists."""
    reg = load_harness_registry(root)
    names = []
    for name in ("codex", "cursor"):
        if name in reg:
            names.append(name)
    for name, h in sorted(reg.items()):
        if name in ("codex", "cursor"):
            continue
        if harness_skills_out(h).is_dir():
            names.append(name)
    return names


# ---------------------------------------------------------------------------
# Profiles (capability -> concrete model bindings)
# ---------------------------------------------------------------------------

@dataclass
class Binding:
    model: str
    reasoning: str | None = None
    service_tier: str | None = None
    fallbacks: list = field(default_factory=list)
    source: str = ""

    def summary(self) -> str:
        return " ".join(x for x in (self.model, self.reasoning, self.service_tier) if x)


@dataclass
class Profile:
    name: str
    path: pathlib.Path
    harness: str
    strict: bool
    main: Binding | None
    capabilities: dict[str, Binding]
    roles: dict[str, dict]
    default: Binding | None


def _binding(raw, where: str, partial: bool = False):
    if not isinstance(raw, dict):
        raise PackError(f"{where}: expected a mapping of {sorted(BINDING_KEYS)}")
    extra = sorted(set(raw) - BINDING_KEYS)
    if extra:
        raise PackError(f"{where}: unknown key(s) {extra}")
    for key in ("model", "reasoning", "service_tier"):
        if key in raw and not isinstance(raw[key], str):
            raise PackError(f"{where}.{key}: expected a string")
    if "fallbacks" in raw and not isinstance(raw["fallbacks"], list):
        raise PackError(f"{where}.fallbacks: expected a list")
    if partial:
        if not raw:
            raise PackError(f"{where}: empty override")
        return dict(raw)
    if not raw.get("model"):
        raise PackError(f"{where}.model is required")
    return Binding(raw["model"], raw.get("reasoning"), raw.get("service_tier"),
                   list(raw.get("fallbacks") or []), where.rsplit(":", 1)[-1])


def available_profiles(root: pathlib.Path) -> list[str]:
    d = root / "profiles"
    return sorted(p.stem for p in d.glob("*.yaml")) if d.is_dir() else []


ACTIVE_DIR = pathlib.Path("profiles") / ".active"


def active_profile_name(root: pathlib.Path, harness: str) -> str | None:
    """Local pointer written by onboard-models --activate (profiles/.active/<harness>)."""
    f = root / ACTIVE_DIR / harness
    if not f.is_file():
        return None
    name = f.read_text().strip()
    return name or None


def load_profile(root: pathlib.Path, name: str, harness: str) -> Profile:
    path = root / "profiles" / f"{name}.yaml"
    if not path.is_file():
        raise PackError(f"profile {name!r} not found at {_short(path)}; "
                        f"available: {', '.join(available_profiles(root)) or 'none'}")
    data = parse_yaml_nested(path.read_text(), str(path))
    tag = _short(path)
    extra = sorted(set(data) - PROFILE_KEYS)
    if extra:
        raise PackError(f"{tag}: unknown top-level key(s) {extra}")
    if data.get("profile") != name:
        raise PackError(f"{tag}: profile {data.get('profile')!r} must match file name {name!r}")
    if data.get("harness") != harness:
        raise PackError(f"{tag}: profile is for harness {data.get('harness')!r}, not {harness!r}")
    strict = data.get("strict", True)
    if not isinstance(strict, bool):
        raise PackError(f"{tag}: strict must be true or false")
    caps_raw = data.get("capabilities") or {}
    if not isinstance(caps_raw, dict):
        raise PackError(f"{tag}: capabilities must be a mapping")
    caps = {}
    for cap, raw in caps_raw.items():
        if cap not in CAPABILITIES:
            raise PackError(f"{tag}: unknown capability {cap!r}; expected one of {', '.join(CAPABILITIES)}")
        caps[cap] = _binding(raw, f"{tag}:capabilities.{cap}")
    roles_raw = data.get("roles") or {}
    if not isinstance(roles_raw, dict):
        raise PackError(f"{tag}: roles must be a mapping")
    roles = {rid: _binding(raw, f"{tag}:roles.{rid}", partial=True) for rid, raw in roles_raw.items()}
    default = _binding(data["default"], f"{tag}:default") if data.get("default") is not None else None
    if strict and default is not None:
        raise PackError(f"{tag}: a strict profile cannot declare default; map each capability explicitly")
    main = _binding(data["main"], f"{tag}:main") if data.get("main") is not None else None
    return Profile(name, path, harness, strict, main, caps, roles, default)


def resolve_agent(profile: Profile, agent: Agent) -> Binding:
    cap = agent.meta["model"]["capability"]
    base = profile.capabilities.get(cap)
    if base is None:
        if profile.strict or profile.default is None:
            mode = "strict" if profile.strict else "no default"
            raise PackError(
                f"profile {profile.name!r} ({mode}) has no binding for capability {cap!r} "
                f"needed by agent {agent.id!r}; add capabilities.{cap} to {_short(profile.path)}"
            )
        base = profile.default
    override = profile.roles.get(agent.id)
    if not override:
        return base
    return Binding(
        override.get("model", base.model),
        override.get("reasoning", base.reasoning),
        override.get("service_tier", base.service_tier),
        list(override.get("fallbacks", base.fallbacks)),
        f"roles.{agent.id} over {base.source}",
    )


def resolve_all(profile: Profile, pack: Pack) -> dict[str, Binding]:
    ids = {a.id for a in pack.agents}
    unknown = sorted(set(profile.roles) - ids)
    if unknown:
        raise PackError(f"{_short(profile.path)}: roles override unknown agent(s) {unknown}")
    return {a.id: resolve_agent(profile, a) for a in pack.agents}


def render_resolved_sidecar(profile: Profile, pack: Pack, resolved: dict[str, Binding]) -> str:
    lines = [
        "# Generated by agent-definition adapters/lib/agentpack.py. Do not edit.",
        ("# Records which profile produced the agent .toml files in this folder." if profile.harness == "codex"
         else "# Records the profile resolution for the skills in this folder (skills-only export)."),
        f"profile: {profile.name}",
        f"source: profiles/{profile.name}.yaml",
        f"strict: {'true' if profile.strict else 'false'}",
        "agents:",
    ]
    for agent in pack.agents:
        b = resolved[agent.id]
        lines.append(f"  {agent.id}: {agent.meta['model']['capability']} -> {b.summary()}  ({b.source})")
    if profile.main is not None:
        lines.append(f"main: {profile.main.summary()}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Tool vocabulary (neutral verbs) and the leak lint
# ---------------------------------------------------------------------------

@dataclass
class ToolMap:
    path: pathlib.Path
    verbs: dict
    leaks: dict  # harness -> list[re.Pattern]
    pending: set
    exempt: list


def load_tool_map(root: pathlib.Path) -> ToolMap | None:
    path = root / TOOL_MAP_PATH
    if not path.is_file():
        return None
    data = parse_yaml_nested(path.read_text(), str(path))
    extra = sorted(set(data) - TOOL_MAP_KEYS)
    if extra:
        raise PackError(f"{path}: unknown key(s) {extra}")
    if str(data.get("schema_version", "")) != "1":
        raise PackError(f"{path}: schema_version must be 1")
    verbs = data.get("verbs")
    if not isinstance(verbs, dict) or not verbs:
        raise PackError(f"{path}: verbs must be a non-empty mapping")
    want = {"meaning", *KNOWN_HARNESSES}
    for verb, entry in verbs.items():
        if not VERB_RE.match(verb):
            raise PackError(f"{path}: verb {verb!r} must be snake_case")
        if not isinstance(entry, dict):
            raise PackError(f"{path}: verbs.{verb} must be a mapping")
        missing, unknown = sorted(want - set(entry)), sorted(set(entry) - want)
        if missing or unknown:
            raise PackError(f"{path}: verbs.{verb} missing {missing} / unknown {unknown}")
        empty = [k for k in sorted(want) if not isinstance(entry[k], str) or not entry[k].strip()]
        if empty:
            raise PackError(f"{path}: verbs.{verb} needs non-empty text for {empty}")
    leaks = {}
    for harness, patterns in (data.get("leaks") or {}).items():
        if harness not in KNOWN_HARNESSES:
            raise PackError(f"{path}: leaks.{harness} is not a known harness ({', '.join(KNOWN_HARNESSES)})")
        if not isinstance(patterns, list):
            raise PackError(f"{path}: leaks.{harness} must be a list")
        compiled = []
        for pat in patterns:
            try:
                compiled.append(re.compile(pat))
            except re.error as exc:
                raise PackError(f"{path}: leaks.{harness} bad regex {pat!r}: {exc}") from None
        leaks[harness] = compiled
    lint = data.get("lint") or {}
    if not isinstance(lint, dict) or set(lint) - TOOL_LINT_KEYS:
        raise PackError(f"{path}: lint takes only {sorted(TOOL_LINT_KEYS)}")
    pending, exempt = lint.get("pending") or [], lint.get("exempt") or []
    if not isinstance(pending, list) or not isinstance(exempt, list):
        raise PackError(f"{path}: lint.pending and lint.exempt must be lists")
    return ToolMap(path, verbs, leaks, set(pending), [e.rstrip("/") for e in exempt])


def _lines_outside_targeted_notes(text: str):
    """(lineno, line) for lines outside "## Harness notes: <names>" sections."""
    in_fence = skipping = False
    for lineno, line in enumerate(text.splitlines(), 1):
        if not in_fence and SECTION_END_RE.match(line):
            skipping = bool(HARNESS_NOTES_RE.match(line))
        if FENCE_RE.match(line):
            in_fence = not in_fence
        if not skipping:
            yield lineno, line


def tool_leaks(pack: Pack, tool_map: ToolMap) -> tuple[list[Finding], dict[str, int]]:
    """Leak findings for skills not pending, plus leak counts for pending skills."""
    ids = {s.id for s in pack.skills}
    unknown = sorted(tool_map.pending - ids)
    if unknown:
        raise PackError(f"{tool_map.path}: lint.pending names unknown skill(s) {unknown}")
    findings: list[Finding] = []
    pending: dict[str, int] = {}
    for skill in pack.skills:
        files = [("BODY.md", skill.root / "BODY.md", skill.body)]
        files += [(rel, src, src.read_text()) for rel, src in skill.companions().items() if src.suffix == ".md"]
        hits = 0
        for rel, src, text in files:
            rel_path = f"{skill.id}/{rel}"
            if any(rel_path == e or rel_path.startswith(e + "/") for e in tool_map.exempt):
                continue
            for lineno, line in _lines_outside_targeted_notes(text):
                for harness, patterns in tool_map.leaks.items():
                    for pat in patterns:
                        m = pat.search(line)
                        if not m:
                            continue
                        hits += 1
                        if skill.id not in tool_map.pending:
                            findings.append(Finding(
                                "leak", src,
                                f"line {lineno}: {harness} tool name {m.group(0)!r}; use a neutral verb "
                                f"(adapters/tool-map.yaml) or move it under '## Harness notes: {harness}'"))
        if skill.id in tool_map.pending:
            if hits:
                pending[skill.id] = hits
            else:
                findings.append(Finding("pending", skill.root,
                                        "listed in lint.pending but has no leaks; remove it from tool-map.yaml"))
    return findings, pending


# ---------------------------------------------------------------------------
# Renderers (native formats)
# ---------------------------------------------------------------------------

def filter_harness_notes(body: str, harness: str | None, where: str = "<body>") -> str:
    """Keep "## Harness notes: <names>" sections only for the target harness.

    A targeted section runs from its heading to the next level-1/2 heading
    outside a code fence. harness=None (portable copy) keeps every section.
    Untargeted "## Harness notes" sections apply everywhere and are kept.
    """
    out: list[str] = []
    in_fence = dropping = False
    for line in body.splitlines(keepends=True):
        text = line.rstrip("\n")
        if not in_fence and SECTION_END_RE.match(text):
            if dropping and out:
                out.append("\n")  # one blank line where the dropped section was
            dropping = False
            m = HARNESS_NOTES_RE.match(text)
            if m:
                names = [n.strip() for n in m.group(1).split(",") if n.strip()]
                unknown = [n for n in names if n not in KNOWN_HARNESSES]
                if not names or unknown:
                    raise PackError(f"{where}: harness notes heading {text!r} must name one or more of "
                                    f"{', '.join(KNOWN_HARNESSES)}")
                if harness is not None and harness not in names:
                    dropping = True
                    while out and not out[-1].strip():
                        out.pop()
                    continue
        if FENCE_RE.match(text):
            in_fence = not in_fence
        if not dropping:
            out.append(line)
    if in_fence:
        raise PackError(f"{where}: unterminated code fence")
    return "".join(out)


def render_skill_md(skill: Skill, harness: str | None = None) -> str:
    name = skill.meta.get("name", skill.id)
    desc = skill.meta.get("description", "")
    body = filter_harness_notes(skill.body, harness, f"skills/{skill.id}/BODY.md")
    return f"---\nname: {name}\ndescription: >-\n  {desc}\n---\n\n{body}"


def render_codex_agent_toml(agent: Agent, binding: Binding) -> str:
    meta = agent.meta
    desc = meta.get("description", "").replace('"', '\\"')
    lines = [f'name = "{meta.get("name", agent.id)}"', f'description = "{desc}"']
    lines.append(f'model = "{binding.model}"')
    if binding.reasoning:
        lines.append(f'model_reasoning_effort = "{binding.reasoning}"')
    if binding.service_tier:
        lines.append(f'service_tier = "{binding.service_tier}"')
        if binding.service_tier == "fast":
            lines.append("features.fast_mode = true")
    sandbox = SANDBOX_MAP.get(meta.get("sandbox", "workspace-write"), "workspace-write")
    lines.append(f'sandbox_mode = "{sandbox}"')
    lines.append('developer_instructions = """')
    lines.append(agent.instructions.rstrip())
    lines.append('"""')
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Desired-tree engine
# ---------------------------------------------------------------------------

@dataclass
class FileSpec:
    data: bytes
    executable: bool = False


@dataclass
class Tree:
    """Files a target root should contain, plus which subtrees it owns."""
    root: pathlib.Path
    files: dict[str, FileSpec] = field(default_factory=dict)
    # Owned entry dirs (skill folders): stale files inside are drift.
    owned_dirs: set[str] = field(default_factory=set)
    # Top-level entries matching this predicate but absent from the pack are orphans.
    orphan_glob: str | None = None
    label: str = ""


@dataclass
class Finding:
    kind: str  # missing | changed | mode | stale | orphan | config | duplicate | leak | pending
    path: pathlib.Path
    detail: str = ""
    want: bytes | None = None
    have: bytes | None = None


def skills_tree(pack: Pack, root: pathlib.Path, label: str, harness: str | None) -> Tree:
    """harness=None is the portable copy: every harness notes section is kept."""
    tree = Tree(root, orphan_glob="*/", label=label)
    for skill in pack.skills:
        tree.owned_dirs.add(skill.id)
        tree.files[f"{skill.id}/SKILL.md"] = FileSpec(render_skill_md(skill, harness).encode())
        for rel, src in skill.companions().items():
            tree.files[f"{skill.id}/{rel}"] = FileSpec(
                src.read_bytes(), executable=os.access(src, os.X_OK)
            )
    return tree


def codex_agents_tree(pack: Pack, root: pathlib.Path, profile: Profile) -> Tree:
    resolved = resolve_all(profile, pack)
    tree = Tree(root, orphan_glob="*.toml", label="codex agents")
    for agent in pack.agents:
        tree.files[f"{agent.id}.toml"] = FileSpec(render_codex_agent_toml(agent, resolved[agent.id]).encode())
    tree.files[RESOLVED_SIDECAR] = FileSpec(render_resolved_sidecar(profile, pack, resolved).encode())
    return tree


def single_file_tree(src: pathlib.Path, dest: pathlib.Path, label: str) -> Tree:
    tree = Tree(dest.parent, label=label)
    tree.files[dest.name] = FileSpec(src.read_bytes())
    return tree


def compare_tree(tree: Tree) -> list[Finding]:
    findings = []
    for rel, spec in sorted(tree.files.items()):
        path = tree.root / rel
        if not path.is_file():
            findings.append(Finding("missing", path, want=spec.data))
            continue
        have = path.read_bytes()
        if have != spec.data:
            findings.append(Finding("changed", path, want=spec.data, have=have))
        elif spec.executable and not os.access(path, os.X_OK):
            findings.append(Finding("mode", path, "should be executable"))
    for owned in sorted(tree.owned_dirs):
        base = tree.root / owned
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            rel_parts = path.relative_to(tree.root).parts
            if any(_is_ignored(pathlib.Path(p)) for p in rel_parts):
                continue
            if path.is_file() and path.relative_to(tree.root).as_posix() not in tree.files:
                findings.append(Finding("stale", path, "not generated from the pack"))
    if tree.orphan_glob and tree.root.is_dir():
        expected_top = {rel.split("/")[0] for rel in tree.files}
        for entry in sorted(tree.root.iterdir()):
            if _is_ignored(entry) or entry.name.startswith(".") or entry.name in expected_top:
                continue
            if tree.orphan_glob == "*/" and entry.is_dir():
                findings.append(Finding("orphan", entry, "skill folder not in the pack"))
            elif tree.orphan_glob == "*.toml" and entry.suffix == ".toml" and entry.is_file():
                findings.append(Finding("orphan", entry, "agent file not in the pack"))
    return findings


def apply_findings(findings: list[Finding], prune: bool, prune_dir: pathlib.Path) -> list[Finding]:
    """Write fixes. Returns findings left unresolved (stale/orphan without --prune)."""
    left = []
    for f in findings:
        if f.kind in ("missing", "changed"):
            f.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = f.path.with_name(f.path.name + ".agentpack-tmp")
            tmp.write_bytes(f.want)
            os.replace(tmp, f.path)
        if f.kind in ("missing", "changed", "mode"):
            continue
        if f.kind in ("stale", "orphan") and prune:
            if _under_home(f.path):
                dest = prune_dir / f.path.relative_to(pathlib.Path.home())
            else:
                dest = prune_dir / f.path.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f.path), str(dest))
            print(f"  pruned {f.kind} {_short(f.path)} -> {_short(dest)}")
            continue
        left.append(f)
    return left


def fix_modes(trees: list[Tree]):
    for tree in trees:
        for rel, spec in tree.files.items():
            path = tree.root / rel
            if spec.executable and path.is_file() and not os.access(path, os.X_OK):
                path.chmod(path.stat().st_mode | 0o111)


def _under_home(path: pathlib.Path) -> bool:
    try:
        path.relative_to(pathlib.Path.home())
        return True
    except ValueError:
        return False


def _short(path: pathlib.Path) -> str:
    s = str(path)
    home = str(pathlib.Path.home())
    return "~" + s[len(home):] if s.startswith(home) else s


# ---------------------------------------------------------------------------
# Codex config.toml owned keys
# ---------------------------------------------------------------------------

def owned_config_keys(fragments: list[pathlib.Path], main: Binding | None = None) -> dict[tuple[str | None, str], object]:
    """(table or None, key) -> value from the profile main binding plus guidance TOML fragments."""
    _need_tomllib()
    owned: dict = {}
    if main is not None:
        owned[(None, "model")] = main.model
        if main.reasoning:
            owned[(None, "model_reasoning_effort")] = main.reasoning
        if main.service_tier:
            owned[(None, "service_tier")] = main.service_tier
            if main.service_tier == "fast":
                owned[("features", "fast_mode")] = True
    from_profile = set(owned)
    for frag in fragments:
        doc = tomllib.loads(frag.read_text())
        for key, value in doc.items():
            if isinstance(value, dict):
                for sub, subval in value.items():
                    if isinstance(subval, dict):
                        raise PackError(f"{frag}: nested table {key}.{sub} not supported")
                    _own(owned, from_profile, (key, sub), subval, frag)
            else:
                _own(owned, from_profile, (None, key), value, frag)
    return owned


def _own(owned: dict, from_profile: set, slot, value, frag):
    if slot in from_profile:
        name = slot[1] if slot[0] is None else f"[{slot[0]}].{slot[1]}"
        raise PackError(f"{frag}: {name} is owned by the profile main block; remove it here")
    owned[slot] = value


def _lookup(doc: dict, table, key):
    scope = doc if table is None else doc.get(table, {})
    return scope.get(key, _MISSING) if isinstance(scope, dict) else _MISSING


_MISSING = object()


def compare_config(config: pathlib.Path, owned: dict) -> list[Finding]:
    _need_tomllib()
    doc = tomllib.loads(config.read_text()) if config.is_file() else {}
    out = []
    for (table, key), want in owned.items():
        have = _lookup(doc, table, key)
        name = key if table is None else f"[{table}].{key}"
        if have is _MISSING:
            out.append(Finding("config", config, f"{name}: missing, pack wants {_toml_value(want)}"))
        elif have != want or type(have) is not type(want):
            out.append(Finding("config", config, f"{name}: installed {_toml_value(have)}, pack wants {_toml_value(want)}"))
    return out


def _toml_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    raise PackError(f"unsupported owned value type {type(v).__name__}")


_HEADER = re.compile(r"^\s*\[\[?\s*([^\]]+?)\s*\]\]?\s*(#.*)?$")


def _section_ranges(lines: list[str]) -> dict[str | None, tuple[int, int]]:
    """Map table name -> (start, end) line indexes; None is the root table."""
    headers = []
    for i, line in enumerate(lines):
        m = _HEADER.match(line)
        if m:
            headers.append((i, m.group(1).replace(" ", "")))
    ranges = {None: (0, headers[0][0] if headers else len(lines))}
    for n, (i, name) in enumerate(headers):
        end = headers[n + 1][0] if n + 1 < len(headers) else len(lines)
        ranges.setdefault(name, (i + 1, end))
    return ranges


def rewrite_config(text: str, owned: dict) -> str:
    """Set owned keys in place; leave every other line untouched."""
    _need_tomllib()
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    for (table, key), want in owned.items():
        ranges = _section_ranges(lines)
        new_line = f"{key} = {_toml_value(want)}\n"
        key_re = re.compile(rf"^\s*{re.escape(key)}\s*=")
        if table not in ranges:
            if lines and lines[-1].strip():
                lines.append("\n")
            lines += [f"[{table}]\n", new_line]
            continue
        start, end = ranges[table]
        hit = next((i for i in range(start, end) if key_re.match(lines[i])), None)
        if hit is not None:
            lines[hit] = new_line
        else:
            insert = end
            while insert > start and not lines[insert - 1].strip():
                insert -= 1
            lines.insert(insert, new_line)
    new_text = "".join(lines)
    # Safety: owned keys now match, and nothing else changed semantically.
    old_doc, new_doc = tomllib.loads(text) if text.strip() else {}, tomllib.loads(new_text)
    for (table, key), want in owned.items():
        if _lookup(new_doc, table, key) != want:
            raise PackError(f"config rewrite failed to set {table}.{key}")
    if _strip_owned(old_doc, owned) != _strip_owned(new_doc, owned):
        raise PackError("config rewrite would change unowned settings; aborting")
    return new_text


def _strip_owned(doc: dict, owned: dict) -> dict:
    import copy
    doc = copy.deepcopy(doc)
    for table, key in owned:
        scope = doc if table is None else doc.get(table)
        if isinstance(scope, dict):
            scope.pop(key, None)
            if table is not None and not scope:
                doc.pop(table, None)
    return doc


def _need_tomllib():
    if tomllib is None:
        raise PackError("Python 3.11+ (tomllib) is required for Codex config sync")


# ---------------------------------------------------------------------------
# Reporting and commands
# ---------------------------------------------------------------------------

def report(findings: list[Finding], show_diff: bool, label: str):
    for f in findings:
        print(f"  DRIFT {f.kind:<8} {_short(f.path)}" + (f"  ({f.detail})" if f.detail else ""))
        if show_diff and f.kind == "changed":
            try:
                a = f.have.decode().splitlines(keepends=True)
                b = f.want.decode().splitlines(keepends=True)
            except UnicodeDecodeError:
                print("    (binary differs)")
                continue
            for line in difflib.unified_diff(a, b, "installed", "pack", n=1):
                sys.stdout.write("    " + line if line.endswith("\n") else "    " + line + "\n")


def run(trees: list[Tree], args, config: tuple[pathlib.Path, dict] | None = None,
        extra_findings: list[Finding] | None = None) -> int:
    prune_dir = pathlib.Path(os.environ.get(
        "AGENTPACK_PRUNE_DIR",
        pathlib.Path.home() / ".agentpack-pruned" / time.strftime("%Y%m%d-%H%M%S"),
    ))
    total_drift = 0
    unresolved: list[Finding] = []
    for tree in trees:
        findings = compare_tree(tree)
        status = "clean" if not findings else f"{len(findings)} drift"
        print(f"{tree.label}: {_short(tree.root)} - {len(tree.files)} files, {status}")
        if args.check or args.dry_run:
            report(findings, args.diff, tree.label)
            total_drift += len(findings)
        else:
            report([f for f in findings if f.kind in ("missing", "changed", "mode")], False, tree.label)
            unresolved += apply_findings(findings, args.prune, prune_dir)
    if not (args.check or args.dry_run):
        fix_modes(trees)
    if config is not None:
        path, owned = config
        findings = compare_config(path, owned)
        keys = ", ".join(k if t is None else f"[{t}].{k}" for t, k in owned)
        print(f"codex config: {_short(path)} - owned keys: {keys}; "
              f"{'clean' if not findings else f'{len(findings)} drift'}")
        report(findings, False, "config")
        if findings:
            if args.check or args.dry_run:
                total_drift += len(findings)
            else:
                old = path.read_text() if path.is_file() else ""
                new = rewrite_config(old, owned)
                if old:
                    backup = path.with_name(path.name + time.strftime(".agentpack-bak-%Y%m%d-%H%M%S"))
                    backup.write_text(old)
                    print(f"  backup {_short(backup)}")
                path.write_text(new)
                print(f"  wrote owned keys into {_short(path)}")
    for f in extra_findings or []:
        print(f"  DRIFT {f.kind:<8} {_short(f.path)}  ({f.detail})")
        total_drift += 1
        unresolved.append(f)

    if args.check:
        print("check: " + ("clean" if not total_drift else f"{total_drift} drift item(s); run the exporter (stale/orphan need --prune)"))
        return 1 if total_drift else 0
    if args.dry_run:
        print(f"dry-run: {total_drift} change(s) pending; nothing written")
        return 0
    if unresolved:
        print(f"export: done; {len(unresolved)} stale/orphan/duplicate/leak item(s) left (rerun with --prune or fix by hand)")
    else:
        print("export: done")
    return 0


def cmd_codex(pack: Pack, args, lint: list[Finding] | None = None) -> int:
    home = pathlib.Path.home()
    codex_home = pathlib.Path(os.environ.get("CODEX_HOME", home / ".codex"))
    agents_out = pathlib.Path(os.environ.get("CODEX_AGENTS_OUT", codex_home / "agents"))
    skills_out = pathlib.Path(os.environ.get("AGENTS_SKILLS_OUT", home / ".agents" / "skills"))
    agents_md = pathlib.Path(os.environ.get("CODEX_AGENTS_MD_OUT", codex_home / "AGENTS.md"))
    config = pathlib.Path(os.environ.get("CODEX_CONFIG", codex_home / "config.toml"))
    parts = set(args.only.split(",")) if args.only else {"agents", "skills", "agents-md", "config"}
    unknown = parts - {"agents", "skills", "agents-md", "config"}
    if unknown:
        raise PackError(f"unknown --only part(s): {sorted(unknown)}")

    profile, resolved = load_and_explain(pack, args, "codex")

    trees, extra = [], list(lint or [])
    if "agents" in parts:
        trees.append(codex_agents_tree(pack, agents_out, profile))
    if "skills" in parts:
        trees.append(skills_tree(pack, skills_out, "codex skills", "codex"))
        # Codex also indexes ~/.codex/skills; a copy there shows duplicates.
        legacy = codex_home / "skills"
        for skill in pack.skills:
            if (legacy / skill.id).exists():
                extra.append(Finding("duplicate", legacy / skill.id,
                                     "also indexed by Codex; remove so the skill is listed once"))
    if "agents-md" in parts:
        trees.append(single_file_tree(pack.root / "AGENTS.md", agents_md, "codex AGENTS.md"))
    cfg = None
    if "config" in parts:
        cfg = (config, owned_config_keys([
            pack.root / "guidance" / "codex-main.toml",
            pack.root / "guidance" / "codex-context.toml",
        ], main=profile.main))
    return run(trees, args, cfg, extra)


def load_and_explain(pack: Pack, args, harness: str) -> tuple[Profile, dict[str, Binding]]:
    # Codex keeps AGENTPACK_PROFILE; other harnesses use <HARNESS>_PROFILE so one env var cannot cross harnesses.
    env = "AGENTPACK_PROFILE" if harness == "codex" else f"{harness.upper()}_PROFILE"
    # Order: --profile, $<HARNESS>_PROFILE, profiles/.active/<harness> (onboard-models --activate), shipping.
    profile = load_profile(pack.root,
                           args.profile or os.environ.get(env) or active_profile_name(pack.root, harness) or harness,
                           harness)
    resolved = resolve_all(profile, pack)
    if harness in CONCRETE_MODEL_HARNESSES:
        bad = [aid for aid, b in resolved.items() if b.model == INHERIT_MODEL]
        if profile.main is not None and profile.main.model == INHERIT_MODEL:
            bad.append("main")
        if bad:
            raise PackError(f"{_short(profile.path)}: {harness} needs concrete models; "
                            f"{INHERIT_MODEL!r} resolved for {bad}")
    print(f"profile: {profile.name} ({'strict' if profile.strict else 'non-strict'}) - "
          f"{len(resolved)} agents resolved from {_short(profile.path)}")
    if args.explain:
        for agent in pack.agents:
            b = resolved[agent.id]
            print(f"  {agent.id:<17} {agent.meta['model']['capability']:<18} -> {b.summary():<28} ({b.source})")
        if profile.main is not None:
            print(f"  {'(main session)':<17} {'':<18} -> {profile.main.summary()}")
    return profile, resolved


def cmd_skills_only(pack: Pack, args, lint: list[Finding] | None, harness_name: str,
                    registry: dict[str, dict]) -> int:
    """Skills-only export for any registered non-cursor harness (grokbot, claude, pi, ...)."""
    if harness_name not in registry:
        raise PackError(f"harness {harness_name!r} is not registered under harnesses/")
    harness = registry[harness_name]
    out = harness_skills_out(harness)
    profile, resolved = load_and_explain(pack, args, harness_name)
    tree = skills_tree(pack, out, f"{harness_name} skills", harness_name)
    tree.files[RESOLVED_SIDECAR] = FileSpec(render_resolved_sidecar(profile, pack, resolved).encode())
    return run([tree], args, extra_findings=list(lint or []))


def cmd_grokbot(pack: Pack, args, lint: list[Finding] | None = None,
                registry: dict[str, dict] | None = None) -> int:
    """Skills-only export for Grok Bot (sand-workflow SKILL.md folders)."""
    return cmd_skills_only(pack, args, lint, "grokbot", registry or {})


def cmd_cursor(pack: Pack, args, lint: list[Finding] | None = None,
               registry: dict[str, dict] | None = None) -> int:
    home = pathlib.Path.home()
    roots = [
        (pathlib.Path(os.environ.get("CURSOR_SKILLS_OUT", home / ".cursor" / "skills")), "cursor skills", "cursor"),
        (pathlib.Path(os.environ.get("PORTABLE_SKILLS_OUT", home / "agents" / "skills")), "portable skills", None),
    ]
    return run([skills_tree(pack, root, label, harness) for root, label, harness in roots], args,
               extra_findings=list(lint or []))


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    root = pathlib.Path(os.environ.get("PACK_ROOT", pathlib.Path(__file__).resolve().parents[2]))

    if argv and argv[0] == "list-harnesses":
        checkable_only = "--checkable" in argv[1:]
        reg = load_harness_registry(root)
        names = checkable_harness_names(root) if checkable_only else sorted(reg)
        for name in names:
            h = reg[name]
            kind = "builtin" if h.get("builtin") else "generic"
            out = harness_skills_out(h)
            print(f"{name}	{kind}	{out}")
        return 0

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    # choices filled after registry load; accept any token here and validate below
    parser.add_argument("harness", help="codex|cursor|grokbot|claude|pi|hermes|<registered> (or list-harnesses)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="compare only; exit 1 on drift")
    mode.add_argument("--dry-run", action="store_true", help="list pending changes; write nothing")
    parser.add_argument("--prune", action="store_true",
                        help="on export, move stale files and orphan skill/agent entries to ~/.agentpack-pruned/<ts>/")
    parser.add_argument("--diff", action="store_true", help="show unified diffs for changed text files")
    parser.add_argument("--only", help="codex only: comma list of agents,skills,agents-md,config")
    parser.add_argument("--profile", help="profile name under profiles/ (default: harness shipping name or $<HARNESS>_PROFILE)")
    parser.add_argument("--explain", action="store_true", help="print each role's capability -> model resolution")
    args = parser.parse_args(argv)
    try:
        registry = load_harness_registry(root)
        if args.harness not in registry and args.harness not in ("codex", "cursor", "grokbot"):
            raise PackError(f"unknown harness {args.harness!r}; registered: {', '.join(sorted(registry)) or 'none'}")
        if args.only and args.harness != "codex":
            parser.error("--only applies to codex")
        if (args.profile or args.explain) and args.harness == "cursor":
            parser.error("--profile/--explain apply to harnesses with a profile (not cursor dual skills export)")
        pack = load_pack(root)
        print(f"pack: {_short(root)} ({len(pack.skills)} skills, {len(pack.agents)} agents)")
        lint: list[Finding] = []
        tool_map = load_tool_map(root)
        if tool_map is not None:
            lint, pending = tool_leaks(pack, tool_map)
            leaks = sum(1 for f in lint if f.kind == "leak")
            line = f"tool vocab: {len(tool_map.verbs)} verbs; {'no leaks' if not leaks else f'{leaks} leak(s)'}"
            if pending:
                line += "; pending: " + ", ".join(f"{k} ({v})" for k, v in sorted(pending.items()))
            print(line)
        if args.harness == "codex":
            return cmd_codex(pack, args, lint)
        if args.harness == "cursor":
            return cmd_cursor(pack, args, lint, registry)
        # Every other registered harness (builtin grokbot or generic claude/pi/hermes/...)
        return cmd_skills_only(pack, args, lint, args.harness, registry)
    except PackError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
