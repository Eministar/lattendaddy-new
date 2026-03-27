from __future__ import annotations

import os
import json
import re
from dataclasses import dataclass
from pathlib import Path

import discord
import httpx

from bot.modules.pasting.formatting.pasting_views import (
    build_pasting_loading_view,
    build_pasting_result_view,
)


_SINGLE_CODE_BLOCK_RE = re.compile(
    r"^\s*```(?P<lang>[a-zA-Z0-9_+.-]*)[ \t]*\n(?P<body>[\s\S]*?)\n?```\s*$"
)
_STACKTRACE_RE = re.compile(
    r"(?im)^(traceback \(most recent call last\):|caused by:|at\s+\S+\(|file \".+\", line \d+)"
)
_LOG_LINE_RE = re.compile(
    r"(?im)^(\[[A-Z]+\]|\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}|\d{2}:\d{2}:\d{2}|\S+\s+(INFO|WARN|ERROR|DEBUG|TRACE)\b|(INFO|WARN|ERROR|DEBUG|TRACE)\b)"
)
_ERROR_WORD_RE = re.compile(
    r"(?i)\b(error|exception|failed|failure|traceback|crash|stack trace|panic|fatal|undefined|cannot|timeout)\b"
)

_TEXT_EXTENSIONS = {
    ".txt", ".log", ".out", ".json", ".jsonl", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".conf", ".env", ".xml", ".html", ".css", ".scss", ".md", ".markdown", ".sql", ".csv",
    ".tsv", ".diff", ".patch", ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".go",
    ".rs", ".php", ".rb", ".c", ".cc", ".cpp", ".cs", ".h", ".hpp", ".sh", ".bash", ".zsh",
    ".ps1", ".bat", ".cmd", ".dockerfile",
}
_LOG_EXTENSIONS = {".log", ".out"}
_CODE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".go", ".rs", ".php", ".rb", ".c",
    ".cc", ".cpp", ".cs", ".h", ".hpp", ".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd",
    ".sql", ".yaml", ".yml", ".json", ".html", ".css", ".scss", ".xml", ".dockerfile",
    ".diff", ".patch",
}
_LANGUAGE_ALIASES = {
    "js": "javascript",
    "mjs": "javascript",
    "cjs": "javascript",
    "ts": "typescript",
    "py": "python",
    "yml": "yaml",
    "md": "markdown",
    "sh": "bash",
    "shell": "bash",
    "ps": "powershell",
    "ps1": "powershell",
    "cmd": "batch",
    "dockerfile": "docker",
}
_EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".ps1": "powershell",
    ".bat": "batch",
    ".cmd": "batch",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
    ".md": "markdown",
    ".markdown": "markdown",
    ".xml": "xml",
    ".diff": "diff",
    ".patch": "diff",
    ".dockerfile": "docker",
}
_LANGUAGE_TO_EXTENSION = {
    "python": ".py",
    "javascript": ".js",
    "typescript": ".ts",
    "json": ".json",
    "yaml": ".yml",
    "bash": ".sh",
    "powershell": ".ps1",
    "sql": ".sql",
    "html": ".html",
    "css": ".css",
    "markdown": ".md",
    "xml": ".xml",
    "diff": ".diff",
    "docker": ".dockerfile",
}
_CODE_PATTERNS = (
    re.compile(r"(?i)\b(def|class|import|from|return|async|await|lambda)\b"),
    re.compile(r"(?i)\b(function|const|let|var|export|module\.exports|console\.log)\b"),
    re.compile(r"(?i)\b(public|private|protected|static|void|new|throws)\b"),
    re.compile(r"(?i)\b(select|insert|update|delete|from|where|join)\b"),
    re.compile(r"(?i)\b(<div|</div>|<span|</span>|<html|<!doctype html)\b"),
    re.compile(r"(?i)\b(package|namespace|using|fn|println!|impl)\b"),
)
_CODE_LINE_PATTERNS = (
    re.compile(r"^\s*(from\s+\S+\s+import\s+\S+|import\s+\S+)\s*$"),
    re.compile(r"^\s*(async\s+def|def|class)\s+\w+"),
    re.compile(r"^\s*(if|elif|else|for|while|try|except|finally|with)\b.*:\s*$"),
    re.compile(r"^\s*return\b"),
    re.compile(r"^\s*[A-Za-z_][A-Za-z0-9_]*\s*=\s*[^=].*$"),
    re.compile(r"^\s*(const|let|var)\s+[A-Za-z_$][A-Za-z0-9_$]*\s*="),
    re.compile(r"^\s*function\s+[A-Za-z_$][A-Za-z0-9_$]*\s*\("),
    re.compile(r"^\s*(public|private|protected)\s+[\w<>\[\], ?]+\s+[A-Za-z_][A-Za-z0-9_]*\s*\("),
    re.compile(r"^\s*(SELECT|INSERT|UPDATE|DELETE|WITH|CREATE|ALTER|DROP)\b", re.IGNORECASE),
    re.compile(r"^\s*</?[A-Za-z][A-Za-z0-9:-]*\b[^>]*>\s*$"),
    re.compile(r"^\s*(FROM|RUN|CMD|ENTRYPOINT|COPY|ADD|WORKDIR|ENV|ARG|EXPOSE|USER)\b", re.IGNORECASE),
    re.compile(r"^\s*[\[\{].*[\]\}]\s*,?\s*$"),
)


class PastingError(RuntimeError):
    pass


@dataclass(slots=True)
class ContentAnalysis:
    content: str
    reason: str
    kind: str | None
    language: str | None


@dataclass(slots=True)
class PasteCandidate:
    title: str
    content: str
    reason: str
    kind: str | None
    language: str | None
    filename: str | None = None


@dataclass(slots=True)
class UploadedPaste:
    title: str
    url: str
    delete_original: bool


class PastingService:
    def __init__(self, bot: discord.Client, settings, logger):
        self.bot = bot
        self.settings = settings
        self.logger = logger
        self._active_messages: set[int] = set()

    def _enabled(self, guild_id: int) -> bool:
        return bool(self.settings.get_guild_bool(guild_id, "pasting.enabled", True))

    def _base_url(self, guild_id: int) -> str:
        raw = (
            str(self.settings.get_guild(guild_id, "pasting.base_url", "") or "").strip()
            or str(os.getenv("STARPASTE_BASE_URL", "") or "").strip()
            or "http://localhost:3000"
        )
        return raw.rstrip("/")

    def _secret(self, guild_id: int) -> str:
        return (
            str(self.settings.get_guild(guild_id, "pasting.discord_integration_secret", "") or "").strip()
            or str(os.getenv("DISCORD_INTEGRATION_SECRET", "") or "").strip()
        )

    def _visibility(self, guild_id: int) -> str:
        raw = str(self.settings.get_guild(guild_id, "pasting.visibility", "unlisted") or "unlisted").strip().lower()
        return raw if raw in {"public", "unlisted"} else "unlisted"

    def _delete_original_enabled(self, guild_id: int) -> bool:
        return bool(self.settings.get_guild_bool(guild_id, "pasting.delete_original", True))

    def _min_characters(self, guild_id: int) -> int:
        try:
            return max(120, int(self.settings.get_guild(guild_id, "pasting.min_characters", 600) or 600))
        except Exception:
            return 600

    def _min_lines(self, guild_id: int) -> int:
        try:
            return max(3, int(self.settings.get_guild(guild_id, "pasting.min_lines", 8) or 8))
        except Exception:
            return 8

    def _max_attachment_bytes(self, guild_id: int) -> int:
        try:
            return max(50000, int(self.settings.get_guild(guild_id, "pasting.max_attachment_bytes", 2000000) or 2000000))
        except Exception:
            return 2000000

    def _ai_detection_enabled(self, guild_id: int) -> bool:
        return bool(self.settings.get_guild_bool(guild_id, "pasting.ai_detection_enabled", True))

    def _ai_detection_max_chars(self, guild_id: int) -> int:
        try:
            return max(800, int(self.settings.get_guild(guild_id, "pasting.ai_detection_max_chars", 2400) or 2400))
        except Exception:
            return 2400

    def _ids_from_setting(self, guild_id: int, key: str) -> set[int]:
        raw = self.settings.get_guild(guild_id, key, []) or []
        out: set[int] = set()
        for item in raw:
            try:
                out.add(int(item))
            except Exception:
                continue
        return out

    def _channel_category_id(self, channel) -> int:
        try:
            category = getattr(channel, "category", None)
            if category and getattr(category, "id", None):
                return int(category.id)
        except Exception:
            pass
        try:
            parent = getattr(channel, "parent", None)
            category = getattr(parent, "category", None)
            if category and getattr(category, "id", None):
                return int(category.id)
        except Exception:
            pass
        return 0

    def _should_ignore_message(self, message: discord.Message) -> bool:
        if not message.guild or message.author.bot or message.webhook_id:
            return True
        if message.id in self._active_messages:
            return True
        guild_id = message.guild.id
        if not self._enabled(guild_id) or not self._secret(guild_id):
            return True
        channel_id = int(getattr(message.channel, "id", 0) or 0)
        if channel_id and channel_id in self._ids_from_setting(guild_id, "pasting.ignored_channel_ids"):
            return True
        category_id = self._channel_category_id(message.channel)
        if category_id and category_id in self._ids_from_setting(guild_id, "pasting.ignored_category_ids"):
            return True
        content = str(message.content or "").lstrip()
        prefixes = list(getattr(self.bot, "prefixes", []) or [])
        return bool(content and any(content.startswith(prefix) for prefix in prefixes if prefix))

    def _normalize_text(self, text: str) -> str:
        return str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip("\n")

    def _normalize_language(self, value: str | None) -> str | None:
        raw = str(value or "").strip().lower()
        if not raw:
            return None
        return _LANGUAGE_ALIASES.get(raw, raw)

    def _strip_single_code_block(self, text: str) -> tuple[str | None, str | None]:
        match = _SINGLE_CODE_BLOCK_RE.match(str(text or ""))
        if not match:
            return None, None
        body = str(match.group("body") or "").strip("\n")
        if not body.strip():
            return None, None
        return body, self._normalize_language(match.group("lang"))

    def _deepseek_service(self, guild_id: int):
        if not self._ai_detection_enabled(guild_id):
            return None
        if not self.settings.get_guild_bool(guild_id, "ai.enabled", True):
            return None
        service = getattr(self.bot, "deepseek_service", None)
        if not service:
            return None
        try:
            if not service._api_key(guild_id):
                return None
        except Exception:
            return None
        return service

    def _classification_excerpt(self, guild_id: int, text: str) -> str:
        value = str(text or "").strip()
        limit = self._ai_detection_max_chars(guild_id)
        if len(value) <= limit:
            return value
        head_limit = int(limit * 0.72)
        tail_limit = max(180, limit - head_limit - 32)
        head = value[:head_limit].rstrip()
        tail = value[-tail_limit:].lstrip()
        return f"{head}\n...[gekürzt]...\n{tail}"

    def _ai_prompt(self, guild_id: int, text: str, *, filename: str | None = None, force: bool = False) -> list[dict]:
        excerpt = self._classification_excerpt(guild_id, text)
        line_count = len([line for line in str(text or "").split("\n") if line.strip()]) or 1
        char_count = len(str(text or ""))
        system_prompt = (
            "Du klassifizierst Inhalte für einen Discord-Paste-Bot.\n"
            "Antworte ausschließlich mit genau einem JSON-Objekt in einer Zeile und ohne Markdown.\n"
            "Schema: "
            "{\"action\":\"upload|ignore\",\"kind\":\"code|log|note\",\"language\":\"typescript|javascript|python|json|bash|powershell|sql|yaml|markdown|html|css|docker|diff|xml|text|null\",\"reason\":\"TypeScript-Code|JavaScript-Code|Python-Code|JSON-Code|Shell-Code|PowerShell-Code|SQL-Code|YAML-Code|Markdown-Code|HTML-Code|CSS-Code|Docker-Code|Diff-Code|XML-Code|Code|Log|Fehlerausgabe|viel Text|Text-Datei\",\"confidence\":0.0}\n"
            "Regeln:\n"
            "- Bevorzuge exakte Sprach-Erkennung. TypeScript und Python niemals verwechseln.\n"
            "- code für echten Quellcode, Konfigurationscode, JSON, SQL, Shell, Dockerfile, Diff, HTML, CSS, XML, Markdown.\n"
            "- log für Logs, Stacktraces, Exceptions, Crash-Reports und technische Fehlerausgaben.\n"
            "- note nur für langen normalen Text.\n"
            "- ignore für kurze normale Nachrichten ohne Paste-Bedarf.\n"
            "- Wenn force_upload=true ist, darf action nicht ignore sein.\n"
            "- language nur setzen, wenn du dir sicher bist, sonst null oder text."
        )
        user_prompt = (
            f"force_upload={str(bool(force)).lower()}\n"
            f"filename={str(filename or '').strip() or 'null'}\n"
            f"char_count={char_count}\n"
            f"line_count={line_count}\n"
            "content:\n"
            f"{excerpt}"
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _parse_ai_json(self, raw: str) -> dict | None:
        text = str(raw or "").strip()
        if not text:
            return None
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else None
        except Exception:
            pass
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def _normalize_ai_analysis(
        self,
        content: str,
        payload: dict | None,
        *,
        filename: str | None = None,
        force: bool = False,
    ) -> ContentAnalysis | None:
        if not isinstance(payload, dict):
            return None

        action = str(payload.get("action") or "").strip().lower()
        if action == "ignore" and not force:
            return None

        kind = str(payload.get("kind") or "").strip().lower()
        if kind not in {"code", "log", "note"}:
            if not force:
                return None
            kind = "note"

        language = self._normalize_language(payload.get("language"))
        if language in {"null", "none", "text"}:
            language = None

        raw_reason = str(payload.get("reason") or "").strip().lower()
        if kind == "code":
            reason = self._code_reason(language)
        elif kind == "log":
            reason = "Fehlerausgabe" if any(token in raw_reason for token in ("fehler", "error", "exception", "stack", "crash")) else "Log"
        else:
            reason = "Text-Datei" if force and filename else "viel Text"

        return ContentAnalysis(content, reason, kind, language)

    async def _analyze_text_with_ai(
        self,
        guild_id: int,
        text: str,
        *,
        filename: str | None = None,
        force: bool = False,
    ) -> ContentAnalysis | None:
        service = self._deepseek_service(guild_id)
        if not service:
            return None

        normalized = self._normalize_text(text)
        if not normalized.strip():
            return None

        upload_text = normalized
        stripped_block, _ = self._strip_single_code_block(normalized)
        if stripped_block:
            upload_text = stripped_block

        try:
            reply, err = await service.complete(
                guild_id,
                self._ai_prompt(guild_id, upload_text, filename=filename, force=force),
                temperature=0.1,
                max_tokens=160,
            )
        except Exception:
            return None

        if err or not reply:
            return None

        return self._normalize_ai_analysis(
            upload_text,
            self._parse_ai_json(reply),
            filename=filename,
            force=force,
        )

    def _infer_language_from_filename(self, filename: str | None) -> str | None:
        raw_name = str(filename or "").strip().lower()
        if raw_name == "dockerfile":
            return "docker"
        suffix = str(Path(str(filename or "")).suffix or "").lower()
        return _EXTENSION_TO_LANGUAGE.get(suffix)

    def _infer_language_from_content(self, text: str) -> str | None:
        stripped = str(text or "").strip()
        if not stripped:
            return None

        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, (dict, list)):
                return "json"
        except Exception:
            pass

        nonempty = [line.strip() for line in stripped.split("\n") if line.strip()]
        if not nonempty:
            return None

        python_hits = sum(
            1 for line in nonempty
            if re.search(r"^(from\s+\S+\s+import\s+\S+|import\s+\S+|async\s+def\s+\w+|def\s+\w+|class\s+\w+|if\s+.+:\s*$|elif\s+.+:\s*$|for\s+.+:\s*$|while\s+.+:\s*$|return\b)", line)
        )
        if python_hits >= 2:
            return "python"

        ts_hits = sum(1 for line in nonempty if re.search(r"^(interface\s+\w+|type\s+\w+\s*=|enum\s+\w+|import\s+.+\s+from\s+['\"]|export\s+(class|function|const|type|interface)\b)", line))
        if ts_hits >= 1 or re.search(r"\b[A-Za-z_][A-Za-z0-9_]*\s*:\s*(string|number|boolean|unknown|any|Record<|Promise<)", stripped):
            return "typescript"

        js_hits = sum(1 for line in nonempty if re.search(r"^(const|let|var|function)\b", line))
        if js_hits >= 1 or "=>" in stripped or "console." in stripped:
            return "javascript"

        sql_hits = sum(1 for line in nonempty if re.search(r"^(SELECT|INSERT|UPDATE|DELETE|WITH|CREATE|ALTER|DROP)\b", line, re.IGNORECASE))
        if sql_hits >= 1:
            return "sql"

        docker_hits = sum(1 for line in nonempty if re.search(r"^(FROM|RUN|CMD|ENTRYPOINT|COPY|ADD|WORKDIR|ENV|ARG|EXPOSE|USER)\b", line, re.IGNORECASE))
        if docker_hits >= 2:
            return "docker"

        if stripped.startswith("#!/") or any(re.search(r"^(echo|cd|export|npm|pnpm|yarn|apt|sudo|cat|grep)\b", line) for line in nonempty):
            return "bash"
        if any(re.search(r"^(\$env:|Write-Host\b|Get-ChildItem\b|Where-Object\b)", line, re.IGNORECASE) for line in nonempty):
            return "powershell"

        html_hits = sum(1 for line in nonempty if re.search(r"^</?[A-Za-z][A-Za-z0-9:-]*\b[^>]*>$", line))
        if html_hits >= 2 or "<!DOCTYPE html>" in stripped.upper():
            return "html"

        yaml_hits = sum(1 for line in nonempty if re.search(r"^[A-Za-z0-9_.\"'-]+\s*:\s*.+$", line))
        if yaml_hits >= 2 and "{" not in stripped and "}" not in stripped:
            return "yaml"

        return None

    def _code_reason(self, language: str | None) -> str:
        if not language:
            return "Code"
        label = {
            "python": "Python-Code",
            "javascript": "JavaScript-Code",
            "typescript": "TypeScript-Code",
            "json": "JSON-Code",
            "yaml": "YAML-Code",
            "bash": "Shell-Code",
            "powershell": "PowerShell-Code",
            "sql": "SQL-Code",
            "html": "HTML-Code",
            "css": "CSS-Code",
            "markdown": "Markdown-Code",
            "xml": "XML-Code",
            "diff": "Diff-Code",
            "docker": "Docker-Code",
        }.get(language)
        return label or f"{language.title()}-Code"

    def _count_code_like_lines(self, text: str) -> tuple[int, int]:
        code_like = 0
        indented = 0
        for line in str(text or "").split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            matched = any(pattern.search(line) for pattern in _CODE_LINE_PATTERNS)
            if matched:
                code_like += 1
            if line.startswith(("    ", "\t")) and (
                matched
                or any(token in stripped for token in ("=", "(", ")", "[", "]", "{", "}", "return", "await", "yield"))
            ):
                indented += 1
        return code_like, indented

    def _score_log(self, text: str, filename: str | None) -> int:
        score = 0
        suffix = str(Path(str(filename or "")).suffix or "").lower()
        if suffix in _LOG_EXTENSIONS:
            score += 2
        log_hits = len(_LOG_LINE_RE.findall(text))
        if log_hits >= 3:
            score += 2
        elif log_hits >= 1:
            score += 1
        if len(re.findall(r"(?i)\b(INFO|WARN|ERROR|DEBUG|TRACE)\b", text)) >= 4:
            score += 1
        return score

    def _score_error(self, text: str, filename: str | None) -> int:
        score = 0
        suffix = str(Path(str(filename or "")).suffix or "").lower()
        if suffix in {".err", ".stacktrace"}:
            score += 2
        stack_hits = len(_STACKTRACE_RE.findall(text))
        if stack_hits >= 2:
            score += 3
        elif stack_hits >= 1:
            score += 2
        if len(_ERROR_WORD_RE.findall(text)) >= 4:
            score += 1
        return score

    def _score_code(self, text: str, filename: str | None, has_code_block: bool, language: str | None) -> int:
        score = 0
        suffix = str(Path(str(filename or "")).suffix or "").lower()
        if has_code_block:
            score += 3
        if language:
            score += 2
        if suffix in _CODE_EXTENSIONS:
            score += 2
        pattern_hits = sum(1 for pattern in _CODE_PATTERNS if pattern.search(text))
        if pattern_hits >= 2:
            score += 2
        elif pattern_hits >= 1:
            score += 1
        code_like_lines, indented_lines = self._count_code_like_lines(text)
        if code_like_lines >= 4:
            score += 4
        elif code_like_lines >= 2:
            score += 2
        elif code_like_lines >= 1:
            score += 1
        if indented_lines >= 3:
            score += 2
        elif indented_lines >= 1:
            score += 1
        if "{" in text and "}" in text and (";" in text or "=>" in text):
            score += 1
        return score

    def _analyze_text(self, guild_id: int, text: str, *, filename: str | None = None, force: bool = False) -> ContentAnalysis | None:
        normalized = self._normalize_text(text)
        if not normalized.strip():
            return None

        upload_text = normalized
        stripped_block, block_language = self._strip_single_code_block(normalized)
        if stripped_block:
            upload_text = stripped_block

        inferred_language = block_language or self._infer_language_from_filename(filename) or self._infer_language_from_content(upload_text)
        content_length = len(upload_text)
        line_count = len([line for line in upload_text.split("\n") if line.strip()]) or 1
        has_code_block = stripped_block is not None or "```" in normalized
        log_score = self._score_log(upload_text, filename)
        error_score = self._score_error(upload_text, filename)
        code_score = self._score_code(upload_text, filename, has_code_block, inferred_language)
        long_text = (
            content_length >= (self._min_characters(guild_id) * 2)
            or (content_length >= self._min_characters(guild_id) and line_count >= self._min_lines(guild_id))
            or (content_length >= (self._min_characters(guild_id) // 2) and line_count >= (self._min_lines(guild_id) * 2))
        )

        if error_score >= 3:
            return ContentAnalysis(upload_text, "Fehlerausgabe", "log", inferred_language)
        if log_score >= 2:
            return ContentAnalysis(upload_text, "Log", "log", inferred_language)
        if code_score >= 4:
            return ContentAnalysis(upload_text, self._code_reason(inferred_language), "code", inferred_language)
        if code_score >= 2 and line_count >= 3:
            return ContentAnalysis(upload_text, self._code_reason(inferred_language), "code", inferred_language)
        if code_score >= 1 and inferred_language and line_count >= 2:
            return ContentAnalysis(upload_text, self._code_reason(inferred_language), "code", inferred_language)
        if error_score >= 2 and line_count >= 3:
            return ContentAnalysis(upload_text, "Fehlerausgabe", "log", inferred_language)
        if long_text:
            return ContentAnalysis(upload_text, "viel Text", "note", inferred_language)
        if force:
            if code_score >= 1:
                return ContentAnalysis(upload_text, self._code_reason(inferred_language), "code", inferred_language)
            if error_score >= 1:
                return ContentAnalysis(upload_text, "Fehlerdatei", "log", inferred_language)
            if log_score >= 1:
                return ContentAnalysis(upload_text, "Log-Datei", "log", inferred_language)
            return ContentAnalysis(upload_text, "Text-Datei", "note", inferred_language)
        return None

    def _extension_for_candidate(self, analysis: ContentAnalysis) -> str:
        if analysis.language and analysis.language in _LANGUAGE_TO_EXTENSION:
            return _LANGUAGE_TO_EXTENSION[analysis.language]
        if analysis.kind == "log":
            return ".log"
        return ".txt"

    def _safe_title(self, value: str, *, fallback: str) -> str:
        title = re.sub(r"[\r\n\t]+", " ", str(value or "")).strip()
        title = re.sub(r"\s+", " ", title)
        if not title:
            title = fallback
        if len(title) <= 80:
            return title
        stem, suffix = os.path.splitext(title)
        if suffix and len(suffix) < 12:
            room = max(1, 80 - len(suffix) - 1)
            return stem[:room].rstrip(" ._-") + "…" + suffix
        return title[:79].rstrip() + "…"

    def _message_title(self, message: discord.Message, analysis: ContentAnalysis) -> str:
        language = str(analysis.language or "").strip().lower()
        reason = str(analysis.reason or "").strip().lower()

        if analysis.kind == "code":
            if language:
                base = f"{language}-code"
            else:
                base = "code-snippet"
        elif analysis.kind == "log":
            if "fehler" in reason:
                base = "fehlerausgabe"
            else:
                base = "logausgabe"
        else:
            if language:
                base = f"{language}-text"
            else:
                base = "textnachricht"

        return self._safe_title(base, fallback="textnachricht")

    def _part_title(self, title: str, index: int, total: int) -> str:
        if total <= 1:
            return self._safe_title(title, fallback="paste.txt")
        stem, suffix = os.path.splitext(title)
        return self._safe_title(
            f"{stem}-teil-{index + 1}-von-{total}{suffix}",
            fallback=f"paste{suffix or '.txt'}",
        )

    def _split_content(self, text: str, limit: int = 20000) -> list[str]:
        value = str(text or "")
        if len(value) <= limit:
            return [value]
        chunks: list[str] = []
        current: list[str] = []
        current_len = 0
        for line in value.splitlines(keepends=True):
            if current and current_len + len(line) > limit:
                chunks.append("".join(current).rstrip("\n"))
                current = []
                current_len = 0
            if len(line) <= limit:
                current.append(line)
                current_len += len(line)
                continue
            start = 0
            while start < len(line):
                piece = line[start:start + limit]
                if current and current_len + len(piece) > limit:
                    chunks.append("".join(current).rstrip("\n"))
                    current = []
                    current_len = 0
                current.append(piece)
                current_len += len(piece)
                if current_len >= limit:
                    chunks.append("".join(current).rstrip("\n"))
                    current = []
                    current_len = 0
                start += limit
        if current:
            chunks.append("".join(current).rstrip("\n"))
        return [chunk for chunk in chunks if chunk]

    def _decode_attachment(self, data: bytes) -> str:
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("utf-8", errors="replace")
            if text.count("\ufffd") > max(3, len(text) // 100):
                try:
                    alt = data.decode("latin-1")
                except Exception:
                    alt = text
                if alt.count("\ufffd") < text.count("\ufffd"):
                    return alt
            return text

    def _is_text_attachment(self, attachment: discord.Attachment) -> bool:
        filename = str(attachment.filename or "").strip()
        if filename.lower() == "dockerfile":
            return True
        suffix = str(Path(filename).suffix or "").lower()
        if suffix in _TEXT_EXTENSIONS:
            return True
        content_type = str(getattr(attachment, "content_type", "") or "").lower()
        if content_type.startswith("text/"):
            return True
        return content_type in {
            "application/json",
            "application/xml",
            "application/javascript",
            "application/x-sh",
            "application/x-powershell",
            "application/sql",
        }

    async def _message_candidate(self, message: discord.Message) -> PasteCandidate | None:
        analysis = await self._analyze_text_with_ai(message.guild.id, message.content or "")
        if not analysis:
            analysis = self._analyze_text(message.guild.id, message.content or "")
        if not analysis:
            return None
        if analysis.kind == "note":
            return None
        return PasteCandidate(
            title=self._message_title(message, analysis),
            content=analysis.content,
            reason=analysis.reason,
            kind=analysis.kind,
            language=analysis.language,
        )

    async def _attachment_candidate(self, message: discord.Message, attachment: discord.Attachment) -> tuple[PasteCandidate | None, str | None]:
        if not self._is_text_attachment(attachment):
            return None, None
        max_bytes = self._max_attachment_bytes(message.guild.id)
        if int(attachment.size or 0) > max_bytes:
            return None, f"{attachment.filename}: Dateianhang ist größer als {max_bytes} Bytes."
        try:
            raw = await attachment.read()
        except Exception:
            return None, f"{attachment.filename}: Dateianhang konnte nicht gelesen werden."
        if not raw:
            return None, None
        decoded = self._decode_attachment(raw)
        analysis = await self._analyze_text_with_ai(
            message.guild.id,
            decoded,
            filename=attachment.filename,
            force=True,
        )
        if not analysis:
            analysis = self._analyze_text(
            message.guild.id,
            decoded,
            filename=attachment.filename,
            force=True,
            )
        if not analysis:
            return None, None
        return (
            PasteCandidate(
                title=self._safe_title(attachment.filename, fallback=f"attachment-{attachment.id}.txt"),
                content=analysis.content,
                reason=analysis.reason,
                kind=analysis.kind,
                language=analysis.language,
                filename=attachment.filename,
            ),
            None,
        )

    async def _collect_candidates(self, message: discord.Message) -> tuple[list[PasteCandidate], list[str]]:
        candidates: list[PasteCandidate] = []
        skipped: list[str] = []

        message_candidate = await self._message_candidate(message)
        if message_candidate:
            candidates.append(message_candidate)

        for attachment in list(message.attachments or []):
            candidate, skip_reason = await self._attachment_candidate(message, attachment)
            if candidate:
                candidates.append(candidate)
            elif skip_reason:
                skipped.append(skip_reason)
        return candidates, skipped

    def _author_name(self, message: discord.Message) -> str:
        author = message.author
        display_name = getattr(author, "display_name", None) or getattr(author, "global_name", None) or author.name
        return str(display_name or author.name)

    def _user_payload(self, message: discord.Message) -> dict:
        payload = {
            "id": str(message.author.id),
            "username": str(getattr(message.author, "name", "") or self._author_name(message)),
            "displayName": self._author_name(message),
        }
        try:
            payload["avatarUrl"] = str(message.author.display_avatar.url)
        except Exception:
            pass
        return payload

    def _message_payload(self, message: discord.Message, filename: str | None, delete_original: bool) -> dict:
        payload: dict[str, object] = {
            "url": message.jump_url,
            "deleteOriginal": bool(delete_original),
        }
        if filename:
            payload["filename"] = filename
        return payload

    def _paste_payload(self, guild_id: int, candidate: PasteCandidate, title: str, content: str) -> dict:
        payload: dict[str, object] = {
            "title": title,
            "content": content,
            "visibility": self._visibility(guild_id),
        }
        if candidate.kind:
            payload["kind"] = candidate.kind
        if candidate.language:
            payload["language"] = candidate.language
        return payload

    def _extract_error_text(self, response: httpx.Response) -> str:
        try:
            data = response.json() or {}
        except Exception:
            data = {}
        for key in ("detail", "message", "error"):
            if key in data and str(data.get(key) or "").strip():
                return str(data.get(key)).strip()
        text = str(response.text or "").strip()
        return text[:240] if text else f"HTTP {response.status_code}"

    async def _resolve_account(self, client: httpx.AsyncClient, message: discord.Message):
        response = await client.post(
            "/api/v1/integrations/discord/accounts/resolve",
            json={"user": self._user_payload(message)},
        )
        if response.status_code >= 400:
            raise PastingError(self._extract_error_text(response))

    async def _upload_candidate(self, client: httpx.AsyncClient, message: discord.Message, candidate: PasteCandidate) -> list[UploadedPaste]:
        uploads: list[UploadedPaste] = []
        parts = self._split_content(candidate.content)
        for index, chunk in enumerate(parts):
            title = self._part_title(candidate.title, index, len(parts))
            response = await client.post(
                "/api/v1/integrations/discord/pastes",
                json={
                    "user": self._user_payload(message),
                    "message": self._message_payload(
                        message,
                        candidate.filename,
                        delete_original=self._delete_original_enabled(message.guild.id),
                    ),
                    "paste": self._paste_payload(message.guild.id, candidate, title, chunk),
                },
            )
            if response.status_code >= 400:
                raise PastingError(self._extract_error_text(response))
            data = response.json() or {}
            bot_actions = data.get("botActions", {}) or {}
            paste = data.get("paste", {}) or {}
            url = str(bot_actions.get("pasteUrl") or "").strip()
            if not url:
                paste_id = str(paste.get("id") or "").strip()
                if paste_id:
                    url = f"{self._base_url(message.guild.id)}/paste/{paste_id}"
            if not url:
                raise PastingError("StarPaste hat keinen Paste-Link zurückgegeben.")
            uploads.append(
                UploadedPaste(
                    title=title,
                    url=url,
                    delete_original=bool(bot_actions.get("deleteOriginal", True)),
                )
            )
        return uploads

    async def _delete_original_message(self, message: discord.Message) -> bool:
        try:
            await message.delete()
            return True
        except Exception:
            return False

    async def _edit_status(self, status_message: discord.Message, view: discord.ui.LayoutView):
        try:
            await status_message.edit(view=view)
        except Exception:
            try:
                await status_message.channel.send(view=view)
            except Exception:
                pass

    async def handle_message(self, message: discord.Message):
        if self._should_ignore_message(message):
            return

        self._active_messages.add(message.id)
        try:
            candidates, skipped_items = await self._collect_candidates(message)
            if not candidates:
                if skipped_items:
                    try:
                        await message.channel.send(
                            view=build_pasting_result_view(
                                self.settings,
                                message.guild,
                                status="error",
                                author_name=self._author_name(message),
                                detected_labels=["kein passender Upload"],
                                links=[],
                                original_deleted=False,
                                skipped_items=skipped_items,
                                error_text="Kein geeigneter Textinhalt konnte an StarPaste übergeben werden.",
                            )
                        )
                    except Exception:
                        pass
                return

            detected_labels = list(dict.fromkeys(candidate.reason for candidate in candidates))
            try:
                status_message = await message.channel.send(
                    view=build_pasting_loading_view(
                        self.settings,
                        message.guild,
                        author_name=self._author_name(message),
                        detected_labels=detected_labels,
                        item_count=len(candidates),
                    )
                )
            except Exception:
                return

            uploaded: list[UploadedPaste] = []
            partial_error: str | None = None

            try:
                async with httpx.AsyncClient(
                    base_url=self._base_url(message.guild.id),
                    headers={"Authorization": f"Bearer {self._secret(message.guild.id)}"},
                    timeout=20.0,
                    follow_redirects=True,
                ) as client:
                    await self._resolve_account(client, message)
                    for candidate in candidates:
                        uploaded.extend(await self._upload_candidate(client, message, candidate))
            except (httpx.HTTPError, PastingError) as exc:
                partial_error = str(exc)

            links = [{"title": item.title, "url": item.url} for item in uploaded]
            if partial_error and not uploaded:
                await self._edit_status(
                    status_message,
                    build_pasting_result_view(
                        self.settings,
                        message.guild,
                        status="error",
                        author_name=self._author_name(message),
                        detected_labels=detected_labels,
                        links=[],
                        original_deleted=False,
                        skipped_items=skipped_items,
                        error_text=partial_error,
                    ),
                )
                try:
                    await self.logger.emit_system(
                        "pasting_upload_failed",
                        {
                            "guild_id": message.guild.id,
                            "channel_id": getattr(message.channel, "id", 0),
                            "message_id": message.id,
                            "error": partial_error,
                        },
                    )
                except Exception:
                    pass
                return

            delete_requested = self._delete_original_enabled(message.guild.id) and uploaded and all(
                item.delete_original for item in uploaded
            )
            original_deleted = await self._delete_original_message(message) if delete_requested and not partial_error else False

            await self._edit_status(
                status_message,
                build_pasting_result_view(
                    self.settings,
                    message.guild,
                    status="partial" if partial_error else "success",
                    author_name=self._author_name(message),
                    detected_labels=detected_labels,
                    links=links,
                    original_deleted=original_deleted,
                    skipped_items=skipped_items,
                    error_text=partial_error,
                ),
            )

            try:
                await self.logger.emit_system(
                    "pasting_upload_completed",
                    {
                        "guild_id": message.guild.id,
                        "channel_id": getattr(message.channel, "id", 0),
                        "message_id": message.id,
                        "pastes": len(uploaded),
                        "status": "partial" if partial_error else "success",
                        "deleted_original": bool(original_deleted),
                    },
                )
            except Exception:
                pass
        finally:
            self._active_messages.discard(message.id)
