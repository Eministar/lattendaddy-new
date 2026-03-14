from __future__ import annotations

import os
import sys
from datetime import datetime


class Console:
    RESET = "\033[0m"
    DIM = "\033[2m"
    BOLD = "\033[1m"

    FG = {
        "red": "\033[38;5;196m",
        "green": "\033[38;5;82m",
        "yellow": "\033[38;5;220m",
        "blue": "\033[38;5;39m",
        "magenta": "\033[38;5;205m",
        "cyan": "\033[38;5;51m",
        "white": "\033[38;5;15m",
        "gray": "\033[38;5;245m",
    }

    def __init__(self):
        self.enabled = self._supports_color()

    def _supports_color(self) -> bool:
        if os.getenv("NO_COLOR"):
            return False
        if os.getenv("FORCE_COLOR"):
            return True
        if not sys.stdout or not getattr(sys.stdout, "isatty", lambda: False)():
            return False
        term = str(os.getenv("TERM", "")).lower()
        if term in {"", "dumb"}:
            return False
        if os.name != "nt":
            return True
        return bool(os.getenv("WT_SESSION") or os.getenv("ANSICON") or os.getenv("ConEmuANSI") == "ON")

    def style(self, text: str, color: str | None = None, bold: bool = False, dim: bool = False) -> str:
        if not self.enabled:
            return text
        seq = ""
        if bold:
            seq += self.BOLD
        if dim:
            seq += self.DIM
        if color:
            seq += self.FG.get(color, "")
        return f"{seq}{text}{self.RESET}"

    def line(self, tag: str, msg: str, color: str = "white"):
        stamp = self.style(datetime.now().strftime("%H:%M:%S"), "gray", dim=True)
        label = self.style(f"[{str(tag).upper():<10}]", color=color, bold=True)
        print(f"{stamp} {label} {msg}")

    def section(self, title: str, subtitle: str | None = None, color: str = "cyan"):
        width = 74
        head = f" {str(title).upper()} "
        tail = f" {subtitle}" if subtitle else ""
        line = (head + tail).strip()
        if len(line) > width:
            line = line[:width]
        fill = "─" * max(0, width - len(line))
        print(self.style(f"{line}{fill}", color=color, bold=True, dim=True))

    def banner(self, app_name: str = "STARRY"):
        width = 70
        top = self.style("╔" + ("═" * width) + "╗", "magenta")
        bot = self.style("╚" + ("═" * width) + "╝", "magenta")
        print(top)
        title = f" {app_name} BOOT SEQUENCE "
        subtitle = " Discord Gateway | Dashboard | Automationen | Moderation "
        footer = " Konfiguration, Dienste und Module werden initialisiert "
        print(
            f"{self.style('║', 'magenta')}"
            f"{self.style(title.center(width), 'cyan', bold=True)}"
            f"{self.style('║', 'magenta')}"
        )
        print(
            f"{self.style('║', 'magenta')}"
            f"{self.style(subtitle.center(width), 'gray')}"
            f"{self.style('║', 'magenta')}"
        )
        print(
            f"{self.style('║', 'magenta')}"
            f"{self.style(footer.center(width), 'white', dim=True)}"
            f"{self.style('║', 'magenta')}"
        )
        print(bot)


console = Console()
