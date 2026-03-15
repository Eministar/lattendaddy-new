from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import discord
import yaml


SYSTEM_MODULE_KEYS = {"bot", "database", "logging"}
SENSITIVE_KEY_PARTS = {"token", "password", "secret", "api_key", "access_key", "client_secret"}
LONG_TEXT_KEY_PARTS = {
    "prompt",
    "description",
    "text",
    "body",
    "template",
    "message",
    "footer",
    "content",
    "system",
    "help",
    "info",
}

MODULE_META: dict[str, dict[str, Any]] = {
    "ai": {"label": "AI / KI", "emoji": "🤖", "aliases": ("ki", "deepseek", "chatbot")},
    "applications": {"label": "Bewerbungen", "emoji": "📝", "aliases": ("bewerbung", "bewerbungen", "application")},
    "automod": {"label": "AutoMod", "emoji": "🛡️", "aliases": ("automod",)},
    "backup": {"label": "Backups", "emoji": "💾", "aliases": ("backups",)},
    "beichte": {"label": "Beichte", "emoji": "🕊️", "aliases": ("confession",)},
    "birthday": {"label": "Geburtstage", "emoji": "🎂", "aliases": ("geburtstag", "birthdays")},
    "bot_status": {"label": "Bot-Status", "emoji": "📡", "aliases": ("status",)},
    "categories": {"label": "Ticket-Kategorien", "emoji": "🧭", "aliases": ("ticket_categories", "kategorien")},
    "counting": {"label": "Counting", "emoji": "🔢", "aliases": ("zaehlen", "zählen")},
    "custom_roles": {"label": "Custom Roles", "emoji": "🎨", "aliases": ("customroles", "custom_role")},
    "design": {"label": "Design", "emoji": "🎨", "aliases": ("layout", "theme")},
    "emoji_quiz": {"label": "Emoji-Quiz", "emoji": "🧠", "aliases": ("emojiquiz", "emoji_quiz")},
    "emojis": {"label": "Emoji-Mapping", "emoji": "🙂", "aliases": ("emoji",)},
    "flags": {"label": "Flaggenquiz", "emoji": "🏳️", "aliases": ("flaggen", "flagquiz")},
    "giveaway": {"label": "Giveaways", "emoji": "🎁", "aliases": ("giveaways",)},
    "guess_number": {"label": "Guess The Number", "emoji": "🔢", "aliases": ("guess", "guess_the_number", "gtn")},
    "invites": {"label": "Invites", "emoji": "📨", "aliases": ("invite",)},
    "moderation": {"label": "Moderation", "emoji": "🔨", "aliases": ("mod", "permissions")},
    "news": {"label": "News", "emoji": "📰", "aliases": ("youtube",)},
    "parlament": {"label": "Parlament", "emoji": "🏛️", "aliases": ("parliament",)},
    "placeholders": {"label": "Placeholders", "emoji": "🧩", "aliases": ("placeholder",)},
    "poll": {"label": "Polls", "emoji": "📊", "aliases": ("polls", "umfrage")},
    "reminder_afk": {"label": "Reminder / AFK", "emoji": "💤", "aliases": ("afk", "reminder")},
    "roles": {"label": "Rollen", "emoji": "🎭", "aliases": ("role", "rollen")},
    "seelsorge": {"label": "Seelsorge", "emoji": "🫶", "aliases": ("care",)},
    "server_guide": {"label": "Server-Guide", "emoji": "📚", "aliases": ("guide", "serverguide")},
    "suggestion": {"label": "Vorschläge", "emoji": "💡", "aliases": ("suggestions", "vorschlaege", "vorschläge")},
    "tempvoice": {"label": "TempVoice", "emoji": "🎤", "aliases": ("temp_voice", "voice")},
    "texts": {"label": "Texte", "emoji": "💬", "aliases": ("text",)},
    "ticket": {"label": "Tickets", "emoji": "🎫", "aliases": ("tickets", "support")},
    "user_stats": {"label": "User-Stats", "emoji": "📈", "aliases": ("stats", "levels", "levelsystem")},
    "welcome": {"label": "Welcome", "emoji": "👋", "aliases": ("welcomes", "willkommen")},
    "wzs": {"label": "Wort zum Sonntag", "emoji": "📖", "aliases": ("wort", "wortzumsonntag", "wort_zum_sonntag", "sonntag", "wordzoomsonntag")},
}


@dataclass(frozen=True, slots=True)
class SettingMeta:
    module_key: str
    relative_path: str
    full_path: str
    kind: str
    element_kind: str | None
    default: Any
    sensitive: bool

    @property
    def leaf_name(self) -> str:
        return self.relative_path.rsplit(".", 1)[-1]

    @property
    def type_label(self) -> str:
        mapping = {
            "bool": "Boolean",
            "int": "Integer",
            "float": "Float",
            "str": "Text",
            "list": f"Liste[{self.element_kind or 'mixed'}]",
            "dict": "Objekt",
            "none": "Optional",
        }
        return mapping.get(self.kind, self.kind)


class SetupService:
    def __init__(self, settings, db):
        self.settings = settings
        self.db = db
        self._example_cache: dict[str, Any] | None = None

    @staticmethod
    def _normalize_lookup(value: str | None) -> str:
        return re.sub(r"[^a-z0-9_]+", "", str(value or "").casefold())

    @staticmethod
    def _humanize_key(value: str) -> str:
        parts = [part for part in str(value or "").replace("_", " ").split() if part]
        if not parts:
            return str(value or "")
        return " ".join(part[:1].upper() + part[1:] for part in parts)

    def _module_info(self, module_key: str) -> dict[str, Any]:
        info = MODULE_META.get(str(module_key), {})
        return {
            "key": str(module_key),
            "label": str(info.get("label") or self._humanize_key(str(module_key))),
            "emoji": str(info.get("emoji") or "⚙️"),
            "aliases": tuple(str(alias) for alias in (info.get("aliases") or ())),
        }

    def _config_tree(self, guild_id: int | None = None) -> dict[str, Any]:
        data = self.settings.dump_guild(int(guild_id)) if guild_id else self.settings.dump()
        return data if isinstance(data, dict) else {}

    def _example_tree(self) -> dict[str, Any]:
        cached = self._example_cache
        if isinstance(cached, dict):
            return deepcopy(cached)
        config_path = Path(str(getattr(self.settings, "config_path", "") or "config/config.yml"))
        example_path = config_path.with_name("config.example.yml")
        if not example_path.exists():
            self._example_cache = {}
            return {}
        try:
            loaded = yaml.safe_load(example_path.read_text(encoding="utf-8")) or {}
        except Exception:
            loaded = {}
        self._example_cache = loaded if isinstance(loaded, dict) else {}
        return deepcopy(self._example_cache)

    def _merge_tree(self, base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
        out = deepcopy(base)
        for key, value in (overlay or {}).items():
            if isinstance(out.get(key), dict) and isinstance(value, dict):
                out[key] = self._merge_tree(out[key], value)
            else:
                out[key] = deepcopy(value)
        return out

    def _schema_tree(self, guild_id: int | None = None) -> dict[str, Any]:
        return self._merge_tree(self._example_tree(), self._config_tree(guild_id=guild_id))

    def _guild_overrides_tree(self, guild_id: int) -> dict[str, Any]:
        data = self.settings.dump_guild_overrides(int(guild_id))
        return data if isinstance(data, dict) else {}

    def module_keys(self) -> list[str]:
        out: list[str] = []
        for key, value in self._schema_tree().items():
            if key in SYSTEM_MODULE_KEYS:
                continue
            if not isinstance(value, dict):
                continue
            out.append(str(key))
        return out

    def module_choices(self, current: str) -> list[tuple[str, str]]:
        term = self._normalize_lookup(current)
        ranked: list[tuple[int, str, str]] = []
        for key in self.module_keys():
            info = self._module_info(key)
            haystack = [key, info["label"], *info["aliases"]]
            normalized = [self._normalize_lookup(item) for item in haystack]
            if term and not any(term in item for item in normalized if item):
                continue
            starts = 0 if any(item.startswith(term) for item in normalized if item and term) else 1
            ranked.append((starts, info["label"], key))
        ranked.sort(key=lambda item: (item[0], item[1], item[2]))
        out: list[tuple[str, str]] = []
        for _, _, key in ranked[:25]:
            info = self._module_info(key)
            out.append((f"{info['emoji']} {info['key']} • {info['label']}", key))
        return out

    def resolve_module_key(self, raw: str | None) -> str | None:
        term = self._normalize_lookup(raw)
        if not term:
            return None
        for key in self.module_keys():
            info = self._module_info(key)
            variants = [key, info["label"], *info["aliases"]]
            if any(term == self._normalize_lookup(variant) for variant in variants):
                return key
        for key in self.module_keys():
            info = self._module_info(key)
            variants = [key, info["label"], *info["aliases"]]
            if any(term in self._normalize_lookup(variant) for variant in variants):
                return key
        return None

    def _infer_kind(self, full_path: str, value: Any) -> tuple[str, str | None]:
        if isinstance(value, bool):
            return "bool", None
        if isinstance(value, int) and not isinstance(value, bool):
            return "int", None
        if isinstance(value, float):
            return "float", None
        if isinstance(value, str):
            return "str", None
        if isinstance(value, dict):
            return "dict", None
        if isinstance(value, list):
            element_kind = None
            for item in value:
                if item is None:
                    continue
                element_kind = self._infer_kind(full_path, item)[0]
                break
            if element_kind is None:
                element_kind = "int" if full_path.endswith("_ids") else "str"
            return "list", element_kind
        return "none", None

    def _is_sensitive(self, full_path: str) -> bool:
        return any(part in str(full_path or "").casefold() for part in SENSITIVE_KEY_PARTS)

    def _collect_setting_metas(self, module_key: str, value: Any, prefix: str = "") -> list[SettingMeta]:
        out: list[SettingMeta] = []
        if isinstance(value, dict):
            if not value and prefix:
                kind, element_kind = self._infer_kind(f"{module_key}.{prefix}", value)
                out.append(
                    SettingMeta(
                        module_key=str(module_key),
                        relative_path=str(prefix),
                        full_path=f"{module_key}.{prefix}",
                        kind=kind,
                        element_kind=element_kind,
                        default=value,
                        sensitive=self._is_sensitive(f"{module_key}.{prefix}"),
                    )
                )
                return out
            for child_key, child_value in value.items():
                next_prefix = f"{prefix}.{child_key}" if prefix else str(child_key)
                out.extend(self._collect_setting_metas(module_key, child_value, next_prefix))
            return out
        kind, element_kind = self._infer_kind(f"{module_key}.{prefix}", value)
        out.append(
            SettingMeta(
                module_key=str(module_key),
                relative_path=str(prefix),
                full_path=f"{module_key}.{prefix}",
                kind=kind,
                element_kind=element_kind,
                default=value,
                sensitive=self._is_sensitive(f"{module_key}.{prefix}"),
            )
        )
        return out

    def setting_metas(self, module_key: str, guild_id: int | None = None) -> list[SettingMeta]:
        data = self._schema_tree(guild_id=guild_id).get(str(module_key))
        if not isinstance(data, dict):
            return []
        metas = self._collect_setting_metas(str(module_key), data)
        return sorted(metas, key=lambda meta: (meta.relative_path.count("."), meta.relative_path))

    def resolve_setting_meta(self, module_key: str, raw: str | None, guild_id: int | None = None) -> SettingMeta | None:
        term = str(raw or "").strip()
        if not term:
            return None
        lowered = term.casefold()
        metas = self.setting_metas(module_key, guild_id=guild_id)
        for meta in metas:
            if lowered == meta.relative_path.casefold() or lowered == meta.full_path.casefold():
                return meta
        leaf_matches = [meta for meta in metas if lowered == meta.leaf_name.casefold()]
        if len(leaf_matches) == 1:
            return leaf_matches[0]
        for meta in metas:
            if lowered in meta.relative_path.casefold():
                return meta
        return None

    def _mask_sensitive(self, value: Any) -> str:
        raw = "" if value is None else str(value)
        if not raw:
            return "••••"
        if len(raw) <= 8:
            return "•" * len(raw)
        return raw[:2] + "…" + raw[-2:]

    def format_value(self, value: Any, meta: SettingMeta, *, limit: int = 120) -> str:
        if meta.sensitive:
            return self._mask_sensitive(value)
        if value is None:
            text = "null"
        elif isinstance(value, bool):
            text = "true" if value else "false"
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            text = str(value)
        elif isinstance(value, str):
            text = value
        else:
            try:
                text = json.dumps(value, ensure_ascii=False)
            except Exception:
                text = str(value)
        text = re.sub(r"\s+", " ", str(text)).strip()
        if len(text) <= limit:
            return text
        return text[: limit - 1].rstrip() + "…"

    def has_override(self, guild_id: int, full_path: str) -> bool:
        sentinel = object()
        return self.settings.get_guild_override(int(guild_id), full_path, sentinel) is not sentinel

    def current_value(self, guild_id: int, meta: SettingMeta) -> Any:
        return self.settings.get_guild(int(guild_id), meta.full_path, meta.default)

    def global_value(self, meta: SettingMeta) -> Any:
        return self.settings.get(meta.full_path, meta.default)

    def module_text(self, guild_id: int, module_key: str) -> str:
        info = self._module_info(module_key)
        lines = [f"# {info['label']} ({module_key})", ""]
        metas = self.setting_metas(module_key, guild_id=guild_id)
        for meta in metas:
            source = "override" if self.has_override(guild_id, meta.full_path) else "global"
            lines.append(
                f"{meta.relative_path} = {self.format_value(self.current_value(guild_id, meta), meta, limit=240)} [{source}]"
            )
        return "\n".join(lines)

    def setting_detail_text(self, guild_id: int, meta: SettingMeta) -> str:
        current_value = self.current_value(guild_id, meta)
        global_value = self.global_value(meta)
        source = "Guild-Override" if self.has_override(guild_id, meta.full_path) else "Global / Basis"
        example = self.example_value(meta)
        lines = [
            f"Modul: `{meta.module_key}`",
            f"Setting: `{meta.relative_path}`",
            f"Pfad: `{meta.full_path}`",
            f"Typ: `{meta.type_label}`",
            f"Quelle: `{source}`",
            f"Aktuell: `{self.format_value(current_value, meta, limit=500)}`",
            f"Global: `{self.format_value(global_value, meta, limit=500)}`",
        ]
        if example:
            lines.append(f"Beispiel: `{example}`")
        return "\n".join(lines)

    def example_value(self, meta: SettingMeta) -> str | None:
        if meta.kind == "bool":
            return "true"
        if meta.kind == "int":
            return "123"
        if meta.kind == "float":
            return "1.5"
        if meta.kind == "str":
            if meta.full_path.endswith("_id"):
                return "123456789012345678"
            return str(meta.default or "Textwert")
        if meta.kind == "dict":
            return "{\"key\": \"value\"}"
        if meta.kind == "list":
            if meta.element_kind == "int":
                return "123,456,789"
            return "eins,zwei,drei"
        if meta.kind == "none":
            return "null"
        return None

    def reference_kind(self, meta: SettingMeta) -> str | None:
        leaf = meta.leaf_name.casefold()
        if leaf.endswith("_channel_id") or leaf.endswith("_channel_ids"):
            return "channel"
        if leaf.endswith("_thread_id") or leaf.endswith("_thread_ids"):
            return "thread"
        if leaf.endswith("_role_id") or leaf.endswith("_role_ids"):
            return "role"
        if leaf.endswith("_user_id") or leaf.endswith("_user_ids"):
            return "user"
        return None

    def editor_kind(self, meta: SettingMeta) -> str:
        reference = self.reference_kind(meta)
        if reference:
            return "reference_multi" if meta.kind == "list" else "reference"
        if meta.sensitive:
            return "secret"
        if meta.kind == "bool":
            return "toggle"
        if meta.kind in {"int", "float"}:
            return "number"
        if meta.kind == "dict":
            return "json"
        if meta.kind == "list":
            if meta.element_kind in {"dict", "list"}:
                return "list_json"
            return "list_text"
        if meta.kind == "none":
            inferred = self._infer_kind(meta.full_path, meta.default)
            if inferred[0] in {"int", "float"}:
                return "number"
            return "text"
        if meta.kind == "str":
            leaf = meta.leaf_name.casefold()
            raw_default = meta.default if isinstance(meta.default, str) else ""
            if leaf.endswith("_url"):
                return "url"
            if any(part in leaf for part in LONG_TEXT_KEY_PARTS):
                return "textarea"
            if "\n" in raw_default or len(raw_default) > 140:
                return "textarea"
            return "text"
        return "text"

    def _safe_raw_value(self, value: Any, meta: SettingMeta) -> Any:
        if meta.sensitive:
            return None
        return self._json_safe_raw(value)

    def _json_safe_raw(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): self._json_safe_raw(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._json_safe_raw(item) for item in value]
        if isinstance(value, tuple):
            return [self._json_safe_raw(item) for item in value]
        if isinstance(value, int) and not isinstance(value, bool) and abs(value) > 9_007_199_254_740_991:
            return str(value)
        return deepcopy(value)

    def _parent_path(self, relative_path: str) -> str | None:
        if "." not in str(relative_path):
            return None
        return str(relative_path).rsplit(".", 1)[0]

    def _setting_label(self, meta: SettingMeta) -> str:
        return self._humanize_key(meta.leaf_name)

    def setting_payload(self, guild_id: int, meta: SettingMeta) -> dict[str, Any]:
        current_value = self.current_value(guild_id, meta)
        global_value = self.global_value(meta)
        override = self.has_override(guild_id, meta.full_path)
        return {
            "module_key": meta.module_key,
            "label": self._setting_label(meta),
            "leaf_name": meta.leaf_name,
            "relative_path": meta.relative_path,
            "parent_path": self._parent_path(meta.relative_path),
            "full_path": meta.full_path,
            "kind": meta.kind,
            "element_kind": meta.element_kind,
            "type_label": meta.type_label,
            "editor_kind": self.editor_kind(meta),
            "reference_kind": self.reference_kind(meta),
            "sensitive": meta.sensitive,
            "override": override,
            "current_display": self.format_value(current_value, meta, limit=300),
            "global_display": self.format_value(global_value, meta, limit=300),
            "current_value": self._safe_raw_value(current_value, meta),
            "global_value": self._safe_raw_value(global_value, meta),
            "default_value": self._safe_raw_value(meta.default, meta),
            "has_value": current_value not in (None, "", [], {}),
            "example": self.example_value(meta),
        }

    def module_summary_payload(self, guild_id: int, module_key: str) -> dict[str, Any]:
        info = self._module_info(module_key)
        metas = self.setting_metas(module_key, guild_id=guild_id)
        override_count = sum(1 for meta in metas if self.has_override(guild_id, meta.full_path))
        return {
            "key": module_key,
            "label": info["label"],
            "emoji": info["emoji"],
            "aliases": list(info["aliases"]),
            "setting_count": len(metas),
            "override_count": override_count,
        }

    def module_payloads(self, guild_id: int) -> list[dict[str, Any]]:
        payloads = [self.module_summary_payload(guild_id, module_key) for module_key in self.module_keys()]
        return sorted(payloads, key=lambda item: ((0 if item["override_count"] else 1), item["label"], item["key"]))

    def module_payload(self, guild_id: int, module_key: str) -> dict[str, Any] | None:
        resolved = self.resolve_module_key(module_key)
        if not resolved:
            return None
        fields = [self.setting_payload(guild_id, meta) for meta in self.setting_metas(resolved, guild_id=guild_id)]
        module = self.module_summary_payload(guild_id, resolved)
        return {
            "module": module,
            "fields": fields,
        }

    def setting_choices(self, guild_id: int, module_key: str, current: str) -> list[tuple[str, str]]:
        term = str(current or "").casefold().strip()
        ranked: list[tuple[int, str, SettingMeta]] = []
        for meta in self.setting_metas(module_key, guild_id=guild_id):
            hay = f"{meta.relative_path} {meta.leaf_name}".casefold()
            if term and term not in hay:
                continue
            starts = 0 if term and meta.relative_path.casefold().startswith(term) else 1
            ranked.append((starts, meta.relative_path, meta))
        ranked.sort(key=lambda item: (item[0], item[1].count("."), item[1]))
        out: list[tuple[str, str]] = []
        for _, _, meta in ranked[:25]:
            preview = self.format_value(self.current_value(guild_id, meta), meta)
            out.append((f"{meta.relative_path} • {preview}", meta.relative_path))
        return out

    def _parse_bool(self, raw: str) -> bool:
        value = str(raw or "").strip().casefold()
        if value in {"true", "1", "yes", "ja", "on", "an", "aktiv"}:
            return True
        if value in {"false", "0", "no", "nein", "off", "aus", "inaktiv"}:
            return False
        raise ValueError("Boolean erwartet: true/false, an/aus, ja/nein.")

    def _parse_int(self, raw: str) -> int:
        text = str(raw or "").strip()
        if re.fullmatch(r"-?\d+", text):
            return int(text)
        match = re.search(r"(\d{2,25})", text)
        if match:
            return int(match.group(1))
        raise ValueError("Integer oder Discord-ID erwartet.")

    def _parse_scalar(self, meta: SettingMeta, raw: str) -> Any:
        text = str(raw or "").strip()
        if meta.kind == "none" and text.casefold() in {"null", "none", "leer"}:
            return None
        if meta.kind == "bool":
            return self._parse_bool(text)
        if meta.kind == "int":
            return self._parse_int(text)
        if meta.kind == "float":
            return float(text.replace(",", "."))
        if meta.kind == "str":
            return text
        if meta.kind == "dict":
            parsed = json.loads(text)
            if not isinstance(parsed, dict):
                raise ValueError("JSON-Objekt erwartet.")
            return parsed
        if meta.kind == "none":
            if meta.full_path.endswith("_id"):
                return self._parse_int(text)
            lowered_path = meta.full_path.casefold()
            lowered_leaf = meta.leaf_name.casefold()
            if lowered_leaf == "enabled" or lowered_leaf.endswith("_enabled") or lowered_leaf.startswith("allow_"):
                return self._parse_bool(text)
            if lowered_leaf.endswith(("_seconds", "_minutes", "_hours", "_days", "_count", "_port", "_level", "_interval", "_timeout")):
                return self._parse_int(text)
            return text
        return text

    def _coerce_list_item(self, raw: str, meta: SettingMeta) -> Any:
        item_meta = SettingMeta(
            module_key=meta.module_key,
            relative_path=meta.relative_path,
            full_path=meta.full_path,
            kind=str(meta.element_kind or "str"),
            element_kind=None,
            default=None,
            sensitive=meta.sensitive,
        )
        return self._parse_scalar(item_meta, raw)

    def _split_csv(self, raw: str) -> list[str]:
        parts = [part.strip() for part in re.split(r"[,;\n]+", str(raw or ""))]
        return [part for part in parts if part]

    def parse_value(self, meta: SettingMeta, raw: str) -> Any:
        if meta.kind != "list":
            return self._parse_scalar(meta, raw)
        text = str(raw or "").strip()
        if text.casefold() in {"[]", "leer", "empty"}:
            return []
        if text.startswith("["):
            parsed = json.loads(text)
            if not isinstance(parsed, list):
                raise ValueError("JSON-Liste erwartet.")
            if meta.element_kind in {"dict", "list"}:
                return parsed
            return [self._coerce_list_item(str(item), meta) for item in parsed]
        if meta.element_kind in {"dict", "list"}:
            raise ValueError("Für diese Liste bitte JSON verwenden.")
        return [self._coerce_list_item(part, meta) for part in self._split_csv(text)]

    async def set_value(self, guild_id: int, meta: SettingMeta, raw: str) -> tuple[Any, str]:
        value = self.parse_value(meta, raw)
        await self.settings.set_guild_override(self.db, int(guild_id), meta.full_path, value)
        return value, f"`{meta.relative_path}` wurde auf `{self.format_value(value, meta, limit=400)}` gesetzt."

    async def reset_value(self, guild_id: int, meta: SettingMeta) -> tuple[bool, str]:
        changed = await self.settings.delete_guild_override(self.db, int(guild_id), meta.full_path)
        if not changed:
            return False, f"`{meta.relative_path}` nutzt bereits den globalen Wert."
        current = self.current_value(guild_id, meta)
        return True, f"`{meta.relative_path}` wurde auf den globalen Wert zurückgesetzt (`{self.format_value(current, meta, limit=400)}`)."

    async def add_list_values(self, guild_id: int, meta: SettingMeta, raw: str) -> tuple[list[Any], str]:
        if meta.kind != "list":
            raise ValueError("`add` funktioniert nur bei Listen-Settings.")
        if meta.element_kind in {"dict", "list"}:
            raise ValueError("Komplexe Listen bitte direkt mit `set` als JSON setzen.")
        current = self.current_value(guild_id, meta)
        if not isinstance(current, list):
            current = []
        incoming = self.parse_value(meta, raw)
        result = list(current)
        for item in incoming:
            if item not in result:
                result.append(item)
        await self.settings.set_guild_override(self.db, int(guild_id), meta.full_path, result)
        return result, f"`{meta.relative_path}` erweitert: `{self.format_value(result, meta, limit=400)}`"

    async def remove_list_values(self, guild_id: int, meta: SettingMeta, raw: str) -> tuple[list[Any], str]:
        if meta.kind != "list":
            raise ValueError("`remove` funktioniert nur bei Listen-Settings.")
        if meta.element_kind in {"dict", "list"}:
            raise ValueError("Komplexe Listen bitte direkt mit `set` als JSON setzen.")
        current = self.current_value(guild_id, meta)
        if not isinstance(current, list):
            current = []
        incoming = self.parse_value(meta, raw)
        result = [item for item in current if item not in incoming]
        await self.settings.set_guild_override(self.db, int(guild_id), meta.full_path, result)
        return result, f"`{meta.relative_path}` reduziert: `{self.format_value(result, meta, limit=400)}`"

    def value_choices(
        self,
        interaction: discord.Interaction,
        meta: SettingMeta | None,
        current: str,
        *,
        mode: str = "set",
    ) -> list[tuple[str, str]]:
        if meta is None or meta.sensitive:
            return []
        guild = interaction.guild
        if guild is None:
            return []
        term = str(current or "").casefold().strip()
        out: list[tuple[str, str]] = []
        if meta.kind == "bool":
            for label, value in (("Aktiviert", "true"), ("Deaktiviert", "false")):
                if term and term not in label.casefold() and term not in value:
                    continue
                out.append((f"{label} • {value}", value))
            return out[:25]

        if mode == "remove" and meta.kind == "list":
            current_value = self.current_value(guild.id, meta)
            if isinstance(current_value, list):
                for item in current_value:
                    candidate = str(item)
                    if term and term not in candidate.casefold():
                        continue
                    out.append((f"Entfernen • {candidate}", candidate))
                    if len(out) >= 25:
                        break
                return out

        if meta.kind == "list" and meta.element_kind == "str":
            current_list = self.current_value(guild.id, meta)
            current_list = current_list if isinstance(current_list, list) else []
            default_value = meta.default if isinstance(meta.default, list) else []
            scalar_defaults = [str(item) for item in default_value if isinstance(item, (str, int, float))]
            seen: set[str] = set()
            if current_list:
                joined = ",".join(str(item) for item in current_list)
                seen.add(joined)
                out.append((f"Aktueller Wert • {joined}", joined))
            for item in scalar_defaults:
                candidate = item
                label = f"{item} • Vorschlag"
                if term and term not in label.casefold() and term not in candidate.casefold():
                    continue
                if candidate in seen:
                    continue
                seen.add(candidate)
                out.append((label, candidate))
                if len(out) >= 25:
                    break
            return out[:25]

        suffix = meta.leaf_name
        if suffix.endswith("_channel_id") or suffix.endswith("_channel_ids"):
            channels = sorted(guild.channels, key=lambda channel: (getattr(channel, "position", 0), channel.id))
            for channel in channels:
                candidate = str(channel.id)
                name = f"#{channel.name} • {channel.id}"
                if term and term not in name.casefold() and term not in candidate.casefold():
                    continue
                out.append((name, candidate))
                if len(out) >= 25:
                    break
            return out

        if suffix.endswith("_thread_id"):
            for thread in sorted(list(guild.threads), key=lambda thread: thread.id):
                candidate = str(thread.id)
                name = f"{thread.name} • {thread.id}"
                if term and term not in name.casefold() and term not in candidate.casefold():
                    continue
                out.append((name, candidate))
                if len(out) >= 25:
                    break
            return out

        if suffix.endswith("_role_id") or suffix.endswith("_role_ids"):
            roles = sorted(list(guild.roles), key=lambda role: role.position, reverse=True)
            for role in roles:
                if role.is_default():
                    continue
                candidate = str(role.id)
                name = f"{role.name} • {role.id}"
                if term and term not in name.casefold() and term not in candidate.casefold():
                    continue
                out.append((name, candidate))
                if len(out) >= 25:
                    break
            return out

        if suffix.endswith("_user_id") or suffix.endswith("_user_ids"):
            members = sorted(list(guild.members), key=lambda member: member.display_name.casefold())
            for member in members:
                candidate = str(member.id)
                name = f"{member.display_name} • {member.id}"
                if term and term not in name.casefold() and term not in candidate.casefold():
                    continue
                out.append((name, candidate))
                if len(out) >= 25:
                    break
            return out

        current_value = self.current_value(guild.id, meta)
        preview = self.format_value(current_value, meta)
        if preview and preview != "null":
            out.append((f"Aktueller Wert • {preview}", preview))
        example = self.example_value(meta)
        if example and example != preview:
            out.append((f"Beispiel • {example}", example))
        return out[:25]
