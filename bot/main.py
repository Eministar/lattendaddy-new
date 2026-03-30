import os
import asyncio
import signal
import traceback
from time import perf_counter
from dotenv import load_dotenv

from bot.core.settings import SettingsManager
from bot.core.db import Database
from bot.core.logger import StarryLogger
from bot.core.bot import StarryBot
from bot.web.server import WebServer
from bot.utils.console import console


def _mask_token(token: str) -> str:
    t = (token or "").strip()
    if len(t) <= 10:
        return "****"
    return t[:4] + "…" + t[-4:]


def _load_token(settings: SettingsManager) -> str:
    cfg_token = str(settings.get("bot.token", "") or "").strip()
    env_token = str(os.getenv("DISCORD_TOKEN", "") or "").strip()

    token = cfg_token if cfg_token else env_token
    if not token:
        raise RuntimeError("Kein Discord Token gefunden. Setz bot.token in config.yml oder DISCORD_TOKEN als Env-Var.")

    if cfg_token:
        console.line(
            "SECURITY",
            f"bot.token aus config.yml aktiv ({_mask_token(cfg_token)}). config.yml nicht committen.",
            color="yellow",
        )
    else:
        console.line("OK", f"Token aus DISCORD_TOKEN aktiv ({_mask_token(env_token)}).", color="green")

    return token


async def main():
    boot_started_at = perf_counter()
    load_dotenv()
    console.banner("STARRY")
    console.section("Core Boot", "Konfiguration • Datenbank • Web • Discord", color="cyan")
    console.line("BOOT", "Lese Konfiguration aus config/config.yml und data/settings.json …", color="cyan")

    settings = SettingsManager(
        config_path="config/config.yml",
        override_path="data/settings.json",
    )
    settings_started_at = perf_counter()
    await settings.load()
    console.line("BOOT", f"Konfiguration geladen ({perf_counter() - settings_started_at:.2f}s).", color="green")

    token = _load_token(settings)

    db_type = str(settings.get("database.type", "sqlite") or "sqlite").lower()
    if db_type == "mysql":
        mysql_cfg = settings.get("database.mysql", {}) or {}
        db = Database(mysql=mysql_cfg)
        console.line("DB", "Backend gewählt: MySQL", color="blue")
    else:
        sqlite_path = str(settings.get("database.sqlite_path", "data/starry.db") or "data/starry.db")
        db = Database(path=sqlite_path)
        console.line("DB", f"Backend gewählt: SQLite ({sqlite_path})", color="blue")
    db_started_at = perf_counter()
    await db.init()
    console.line("DB", f"Verbindung initialisiert ({perf_counter() - db_started_at:.2f}s).", color="green")
    overrides_started_at = perf_counter()
    await settings.load_guild_overrides(db)
    console.line("BOOT", f"Guild-Overrides geladen ({perf_counter() - overrides_started_at:.2f}s).", color="green")

    logger = StarryLogger(settings=settings, db=db)

    bot = StarryBot(settings=settings, db=db, logger=logger)

    web = WebServer(settings=settings, db=db, bot=bot)

    stop_event = asyncio.Event()

    def _request_shutdown():
        if not stop_event.is_set():
            try:
                console.line("STOP", "Shutdown-Signal empfangen …", color="yellow")
            except Exception:
                pass
            stop_event.set()

    try:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _request_shutdown)
            except NotImplementedError:
                pass
    except Exception:
        pass

    console.section("Service Start", "Dashboard und Discord werden hochgefahren", color="blue")
    web_started_at = perf_counter()
    await web.start()
    dash_bind_host = web.dashboard_bind_host()
    dash_port = web.dashboard_port()
    dash_public_url = web.dashboard_public_base_url()
    console.line("WEB", f"Dashboard bindet auf {dash_bind_host}:{dash_port} ({perf_counter() - web_started_at:.2f}s).", color="green")
    console.line("WEB", f"Dashboard öffentlich unter {dash_public_url}", color="blue")
    console.line("BOOT", "Discord-Gateway-Login startet …", color="cyan")

    async def _run_bot():
        try:
            await bot.start(token)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            console.line("ERROR", f"Bot-Start fehlgeschlagen ({type(exc).__name__}): {exc}", color="red")
            traceback.print_exc()
            raise

    bot_task = asyncio.create_task(_run_bot())
    stop_task = asyncio.create_task(stop_event.wait())
    bot_error: BaseException | None = None

    done, pending = await asyncio.wait(
        {bot_task, stop_task},
        return_when=asyncio.FIRST_COMPLETED
    )

    if bot_task in done:
        try:
            bot_task.result()
        except BaseException as exc:
            bot_error = exc

    if stop_task in done and not bot_task.done():
        console.section("Shutdown", "Beende Dienste sauber", color="yellow")
        console.line("STOP", "Bot wird sauber beendet …", color="yellow")
        try:
            await bot.close()
        except Exception:
            pass
    elif bot_error is not None:
        try:
            if not bot.is_closed():
                await bot.close()
        except Exception:
            pass

    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    try:
        console.line("WEB", "Dashboard wird gestoppt …", color="yellow")
        await web.stop()
        console.line("WEB", "Dashboard gestoppt.", color="green")
    except Exception:
        pass

    try:
        console.line("DB", "Datenbankverbindung wird geschlossen …", color="yellow")
        await db.close()
        console.line("DB", "Datenbankverbindung geschlossen.", color="green")
    except Exception:
        pass

    try:
        total_runtime = perf_counter() - boot_started_at
        console.line("BYE", f"Shutdown abgeschlossen. Gesamtlaufzeit: {total_runtime:.2f}s.", color="magenta")
    except Exception:
        pass

    if bot_error is not None:
        raise bot_error


if __name__ == "__main__":
    asyncio.run(main())
