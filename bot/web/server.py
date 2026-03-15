import os
import json
import asyncio
import time
import secrets
import discord
import httpx
from datetime import timedelta
from urllib.parse import urlencode, urlparse
from fastapi import FastAPI, Request, HTTPException, WebSocket
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from bot.modules.tickets.services.ticket_service import TicketService
from bot.modules.moderation.services.mod_service import ModerationService
from bot.modules.birthdays.services.birthday_service import BirthdayService
from bot.modules.setup.services.setup_service import SetupService, SettingMeta


class WebServer:
    def __init__(self, settings, db, bot):
        self.settings = settings
        self.db = db
        self.bot = bot
        self.ticket_service = TicketService(bot, settings, db, getattr(bot, "logger", None))
        self.moderation_service = ModerationService(bot, settings, db, getattr(bot, "forum_logs", None))
        self.birthday_service = getattr(bot, "birthday_service", None) or BirthdayService(bot, settings, db, getattr(bot, "logger", None))
        self.setup_service = getattr(bot, "setup_service", None) or SetupService(settings, db)
        self.app = FastAPI()
        self._server = None
        self._task = None

        base = os.path.dirname(__file__)
        static_dir = os.path.join(base, "static")

        self.app.mount("/static", StaticFiles(directory=static_dir), name="static")

        @self.app.get("/")
        async def index():
            return FileResponse(
                os.path.join(static_dir, "index.html"),
                headers={
                    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                    "Pragma": "no-cache",
                    "Expires": "0",
                },
            )

        @self.app.get("/login")
        async def login():
            auth_url = self._discord_oauth_url()
            return RedirectResponse(auth_url)

        @self.app.get("/logout")
        async def logout(request: Request):
            session_id = request.cookies.get(self._session_cookie_name())
            if session_id:
                await self.db.delete_dashboard_session(session_id)
            resp = RedirectResponse("/")
            resp.delete_cookie(self._session_cookie_name())
            return resp

        @self.app.get("/oauth/callback")
        async def oauth_callback(request: Request, code: str | None = None):
            if not code:
                raise HTTPException(status_code=400, detail="Missing code")
            token_data = await self._exchange_code(code)
            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token")
            expires_in = int(token_data.get("expires_in") or 0)
            if not access_token or not expires_in:
                raise HTTPException(status_code=400, detail="OAuth failed")

            user = await self._fetch_user(access_token)
            guilds = await self._fetch_guilds(access_token)

            session_id = secrets.token_urlsafe(32)
            expires_at = int(time.time()) + int(expires_in)
            await self.db.upsert_dashboard_session(
                session_id=session_id,
                user_id=int(user.get("id")),
                username=str(user.get("username")),
                avatar=str(user.get("avatar") or ""),
                access_token=str(access_token),
                refresh_token=str(refresh_token) if refresh_token else None,
                expires_at=expires_at,
                guilds_json=json.dumps(guilds, ensure_ascii=False),
            )

            resp = RedirectResponse("/")
            resp.set_cookie(
                self._session_cookie_name(),
                session_id,
                httponly=True,
                samesite="lax",
                max_age=int(expires_in),
            )
            return resp

        @self.app.get("/api/me")
        async def me(request: Request):
            session = await self._require_session(request)
            return JSONResponse(self._json_safe(self._session_payload(session)))

        @self.app.get("/api/guilds")
        async def list_guilds(request: Request):
            session = await self._require_session(request)
            return JSONResponse(self._json_safe(self._accessible_guilds(session)))

        @self.app.get("/api/global/summary")
        async def global_summary(request: Request):
            await self._require_session(request)
            tickets = await self.db.count_tickets_by_status()
            giveaways = await self.db.count_giveaways()
            polls = await self.db.count_polls()
            applications = await self.db.count_applications()
            birthdays = await self.db.count_birthdays_global()
            return JSONResponse({
                "tickets": tickets,
                "giveaways": giveaways,
                "polls": polls,
                "applications": applications,
                "birthdays": birthdays,
            })

        @self.app.get("/api/guilds/{guild_id}/summary")
        async def guild_summary(request: Request, guild_id: int):
            await self._require_guild_access(request, guild_id)
            tickets = await self.db.count_tickets_by_status_for_guild(int(guild_id))
            giveaways = await self.db.count_giveaways(int(guild_id))
            polls = await self.db.count_polls(int(guild_id))
            applications = await self.db.count_applications(int(guild_id))
            return JSONResponse({
                "tickets": tickets,
                "giveaways": giveaways,
                "polls": polls,
                "applications": applications,
            })

        @self.app.get("/api/guilds/{guild_id}/settings")
        async def get_guild_settings(request: Request, guild_id: int):
            await self._require_guild_access(request, guild_id)
            return JSONResponse(self.settings.dump_guild(int(guild_id)))

        @self.app.get("/api/guilds/{guild_id}/meta")
        async def get_guild_meta(request: Request, guild_id: int):
            guild = await self._require_guild_access(request, guild_id)
            return JSONResponse(self._json_safe(self._guild_meta_payload(guild)))

        @self.app.get("/api/guilds/{guild_id}/overrides")
        async def get_guild_overrides(request: Request, guild_id: int):
            await self._require_guild_access(request, guild_id)
            return JSONResponse(self.settings.dump_guild_overrides(int(guild_id)))

        @self.app.put("/api/guilds/{guild_id}/overrides")
        async def put_guild_overrides(request: Request, guild_id: int):
            await self._require_guild_access(request, guild_id)
            data = await request.json()
            if not isinstance(data, dict):
                raise HTTPException(status_code=400, detail="Invalid settings payload")
            await self.settings.replace_guild_overrides(self.db, int(guild_id), data)
            return JSONResponse({"ok": True})


        @self.app.get("/api/guilds/{guild_id}/resources")
        async def get_guild_resources(request: Request, guild_id: int):
            guild = await self._require_guild_access(request, guild_id)
            channels = []
            for channel in sorted(list(guild.channels), key=lambda item: (getattr(item, "position", 0), item.id)):
                parent = getattr(channel, "category", None)
                channels.append({
                    "id": int(channel.id),
                    "name": str(channel.name),
                    "type": str(getattr(getattr(channel, "type", None), "name", "unknown")),
                    "position": int(getattr(channel, "position", 0) or 0),
                    "parent_id": int(parent.id) if parent else 0,
                    "parent_name": str(parent.name) if parent else "",
                    "mention": getattr(channel, "mention", f"<#${channel.id}>").replace('$', ''),
                })
            threads = []
            for thread in sorted(list(guild.threads), key=lambda item: item.id):
                parent = getattr(thread, "parent", None)
                threads.append({
                    "id": int(thread.id),
                    "name": str(thread.name),
                    "parent_id": int(parent.id) if parent else 0,
                    "parent_name": str(parent.name) if parent else "",
                    "mention": getattr(thread, "mention", f"<#${thread.id}>").replace('$', ''),
                })
            roles = []
            for role in sorted(list(guild.roles), key=lambda item: item.position, reverse=True):
                if role.is_default():
                    continue
                roles.append({
                    "id": int(role.id),
                    "name": str(role.name),
                    "position": int(role.position or 0),
                    "mention": str(role.mention),
                    "color": str(role.color),
                })
            members = []
            for member in sorted(list(guild.members), key=lambda item: item.display_name.casefold()):
                avatar_url = ""
                try:
                    avatar_url = str(member.display_avatar.replace(size=128, format="webp").url)
                except Exception:
                    try:
                        avatar_url = str(member.display_avatar.url)
                    except Exception:
                        avatar_url = ""
                members.append({
                    "id": int(member.id),
                    "name": str(member.name),
                    "display_name": str(member.display_name),
                    "mention": str(member.mention),
                    "avatar_url": avatar_url,
                })
            return JSONResponse(self._json_safe({
                "guild": {
                    "id": int(guild.id),
                    "name": str(guild.name),
                },
                "channels": channels,
                "threads": threads,
                "roles": roles,
                "members": members,
            }))

        @self.app.get("/api/guilds/{guild_id}/modules")
        async def list_modules(request: Request, guild_id: int):
            await self._require_guild_access(request, guild_id)
            payload = [
                self._serialize_setup_module(int(guild_id), module_key, include_settings=False)
                for module_key in self.setup_service.module_keys()
            ]
            return JSONResponse(self._json_safe(payload))

        @self.app.get("/api/guilds/{guild_id}/setup/modules")
        async def list_modules_legacy(request: Request, guild_id: int):
            await self._require_guild_access(request, guild_id)
            return JSONResponse(self._json_safe(self.setup_service.module_payloads(int(guild_id))))

        @self.app.get("/api/guilds/{guild_id}/modules/{module_key}")
        async def get_module(request: Request, guild_id: int, module_key: str):
            await self._require_guild_access(request, guild_id)
            resolved = self.setup_service.resolve_module_key(module_key)
            if not resolved:
                raise HTTPException(status_code=404, detail="Module not found")
            return JSONResponse(self._json_safe(self._serialize_setup_module(int(guild_id), resolved, include_settings=True)))

        @self.app.get("/api/guilds/{guild_id}/setup/modules/{module_key}")
        async def get_module_legacy(request: Request, guild_id: int, module_key: str):
            await self._require_guild_access(request, guild_id)
            payload = self.setup_service.module_payload(int(guild_id), module_key)
            if not payload:
                raise HTTPException(status_code=404, detail="Module not found")
            return JSONResponse(self._json_safe(payload))

        @self.app.post("/api/guilds/{guild_id}/modules/{module_key}/set")
        async def set_module_setting(request: Request, guild_id: int, module_key: str):
            await self._require_guild_access(request, guild_id)
            data = await request.json()
            _resolved, meta = self._require_setup_meta(int(guild_id), module_key, data.get("setting"))
            try:
                _value, message = await self.setup_service.set_value(
                    int(guild_id),
                    meta,
                    self._setup_raw_value(data.get("value")),
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return JSONResponse({
                "ok": True,
                "message": message,
                "setting": self._serialize_setup_setting(int(guild_id), meta),
            })

        @self.app.post("/api/guilds/{guild_id}/modules/{module_key}/add")
        async def add_module_setting(request: Request, guild_id: int, module_key: str):
            await self._require_guild_access(request, guild_id)
            data = await request.json()
            _resolved, meta = self._require_setup_meta(int(guild_id), module_key, data.get("setting"))
            try:
                _value, message = await self.setup_service.add_list_values(
                    int(guild_id),
                    meta,
                    self._setup_raw_value(data.get("value")),
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return JSONResponse({
                "ok": True,
                "message": message,
                "setting": self._serialize_setup_setting(int(guild_id), meta),
            })

        @self.app.post("/api/guilds/{guild_id}/modules/{module_key}/remove")
        async def remove_module_setting(request: Request, guild_id: int, module_key: str):
            await self._require_guild_access(request, guild_id)
            data = await request.json()
            _resolved, meta = self._require_setup_meta(int(guild_id), module_key, data.get("setting"))
            try:
                _value, message = await self.setup_service.remove_list_values(
                    int(guild_id),
                    meta,
                    self._setup_raw_value(data.get("value")),
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return JSONResponse({
                "ok": True,
                "message": message,
                "setting": self._serialize_setup_setting(int(guild_id), meta),
            })

        @self.app.post("/api/guilds/{guild_id}/modules/{module_key}/reset")
        async def reset_module_setting(request: Request, guild_id: int, module_key: str):
            await self._require_guild_access(request, guild_id)
            data = await request.json()
            _resolved, meta = self._require_setup_meta(int(guild_id), module_key, data.get("setting"))
            changed, message = await self.setup_service.reset_value(int(guild_id), meta)
            return JSONResponse({
                "ok": True,
                "changed": bool(changed),
                "message": message,
                "setting": self._serialize_setup_setting(int(guild_id), meta),
            })

        @self.app.post("/api/guilds/{guild_id}/setup/action")
        async def setup_action_legacy(request: Request, guild_id: int):
            await self._require_guild_access(request, guild_id)
            data = await request.json()
            module_key = str(data.get("module") or data.get("module_key") or "").strip()
            action = str(data.get("action") or "").strip().lower()
            _resolved, meta = self._require_setup_meta(int(guild_id), module_key, data.get("setting"))

            try:
                if action == "set":
                    _value, message = await self.setup_service.set_value(
                        int(guild_id),
                        meta,
                        self._setup_raw_value(data.get("value")),
                    )
                    changed = True
                elif action == "add":
                    _value, message = await self.setup_service.add_list_values(
                        int(guild_id),
                        meta,
                        self._setup_raw_value(data.get("value")),
                    )
                    changed = True
                elif action == "remove":
                    _value, message = await self.setup_service.remove_list_values(
                        int(guild_id),
                        meta,
                        self._setup_raw_value(data.get("value")),
                    )
                    changed = True
                elif action == "reset":
                    changed, message = await self.setup_service.reset_value(int(guild_id), meta)
                else:
                    raise HTTPException(status_code=400, detail="Unsupported setup action")
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

            return JSONResponse({
                "ok": True,
                "changed": bool(changed),
                "message": message,
                "setting": self._serialize_setup_setting(int(guild_id), meta),
            })


        @self.app.get("/api/guilds/{guild_id}/tickets")
        async def list_tickets(request: Request, guild_id: int, limit: int = 200):
            await self._require_guild_access(request, guild_id)
            rows = await self.db.list_tickets_for_guild(int(guild_id), limit=limit)
            out = []
            for r in rows:
                out.append({
                    "id": r[0],
                    "user_id": r[1],
                    "thread_id": r[2],
                    "status": r[3],
                    "claimed_by": r[4],
                    "created_at": r[5],
                    "closed_at": r[6],
                    "rating": r[7]
                })
            return JSONResponse(self._json_safe(out))

        @self.app.get("/api/logs")
        async def list_logs(request: Request, limit: int = 200):
            await self._require_session(request)
            rows = await self.db.list_logs(limit=limit)
            out = []
            for r in rows:
                out.append({
                    "id": r[0],
                    "event": r[1],
                    "payload": r[2],
                    "created_at": r[3],
                })
            return JSONResponse(out)

        @self.app.get("/api/guilds/{guild_id}/snippets")
        async def get_snippets(request: Request, guild_id: int):
            await self._require_guild_access(request, guild_id)
            data = self.settings.get_guild(int(guild_id), "ticket.snippets", {}) or {}
            return JSONResponse(data)

        @self.app.put("/api/guilds/{guild_id}/snippets")
        async def put_snippets(request: Request, guild_id: int):
            await self._require_guild_access(request, guild_id)
            data = await request.json()
            if not isinstance(data, dict):
                raise HTTPException(status_code=400, detail="Invalid snippets payload")
            await self.settings.set_guild_override(self.db, int(guild_id), "ticket.snippets", data)
            return JSONResponse({"ok": True})

        @self.app.get("/api/guilds/{guild_id}/applications")
        async def get_applications(request: Request, guild_id: int):
            await self._require_guild_access(request, guild_id)
            data = self.settings.get_guild(int(guild_id), "applications", {}) or {}
            return JSONResponse(data)

        @self.app.put("/api/guilds/{guild_id}/applications")
        async def put_applications(request: Request, guild_id: int):
            await self._require_guild_access(request, guild_id)
            data = await request.json()
            if not isinstance(data, dict):
                raise HTTPException(status_code=400, detail="Invalid applications payload")
            await self.settings.set_guild_override(self.db, int(guild_id), "applications", data)
            return JSONResponse({"ok": True})

        @self.app.get("/api/guilds/{guild_id}/applications/list")
        async def list_applications(request: Request, guild_id: int, limit: int = 200):
            await self._require_guild_access(request, guild_id)
            rows = await self.db.list_applications_for_guild(int(guild_id), limit=limit)
            out = []
            for r in rows:
                out.append({
                    "id": r[0],
                    "user_id": r[1],
                    "thread_id": r[2],
                    "status": r[3],
                    "created_at": r[4],
                    "closed_at": r[5],
                })
            return JSONResponse(self._json_safe(out))

        @self.app.get("/api/global/birthdays")
        async def list_global_birthdays(request: Request, limit: int = 25, offset: int = 0):
            await self._require_session(request)
            rows = await self.db.list_birthdays_global(limit=limit, offset=offset)
            total = await self.db.count_birthdays_global()
            out = []
            for r in rows:
                user_payload = await self._user_brief(r[0])
                out.append({
                    "user_id": r[0],
                    "day": r[1],
                    "month": r[2],
                    "year": r[3],
                    "username": user_payload["username"],
                    "display_name": user_payload["display_name"],
                    "avatar_url": user_payload["avatar_url"],
                })
            return JSONResponse(self._json_safe({"total": total, "items": out}))

        @self.app.get("/api/guilds/{guild_id}/birthdays/live")
        async def live_birthdays(request: Request, guild_id: int):
            guild = await self._require_guild_access(request, guild_id)
            payload = await self.birthday_service.build_dashboard_payload(guild)
            return JSONResponse(self._json_safe(payload))

        @self.app.get("/api/guilds/{guild_id}/birthdays/summary")
        async def guild_birthdays_summary(request: Request, guild_id: int):
            guild = await self._require_guild_access(request, guild_id)
            payload = await self.birthday_service.build_dashboard_payload(guild)
            return JSONResponse(self._json_safe(payload))

        @self.app.websocket("/ws/logs")
        async def ws_logs(websocket: WebSocket):
            session = await self._require_socket_session(websocket)
            await websocket.accept()
            last_id = 0
            try:
                while True:
                    rows = await self.db.list_logs(limit=50)
                    rows = list(reversed(rows))
                    for r in rows:
                        if int(r[0]) <= last_id:
                            continue
                        payload = {"id": r[0], "event": r[1], "payload": r[2], "created_at": r[3]}
                        await websocket.send_json(payload)
                        last_id = int(r[0])
                    await asyncio.sleep(2.0)
            except Exception:
                try:
                    await websocket.close()
                except Exception:
                    pass

        @self.app.get("/api/guilds/{guild_id}/users/search")
        async def search_users(request: Request, guild_id: int, query: str):
            guild = await self._require_guild_access(request, guild_id)
            q = (query or "").lower()
            out = []
            for m in guild.members:
                if q in str(m.id) or q in m.name.lower() or q in m.display_name.lower():
                    out.append({"id": m.id, "name": m.name, "display_name": m.display_name})
                    if len(out) >= 25:
                        break
            return JSONResponse(self._json_safe(out))

        @self.app.get("/api/guilds/{guild_id}/users/live")
        async def live_users(request: Request, guild_id: int, limit: int = 50):
            guild = await self._require_guild_access(request, guild_id)
            out = []
            for m in guild.members:
                if m.status in (discord.Status.online, discord.Status.idle, discord.Status.dnd):
                    out.append({
                        "id": m.id,
                        "name": m.name,
                        "display_name": m.display_name,
                        "status": str(m.status)
                    })
                if len(out) >= limit:
                    break
            return JSONResponse(self._json_safe(out))

        @self.app.post("/api/guilds/{guild_id}/discord/message")
        async def send_message(request: Request, guild_id: int):
            guild = await self._require_guild_access(request, guild_id)
            data = await request.json()
            channel_id = self._int(data.get("channel_id", 0))
            content = str(data.get("content", "")).strip()
            if not channel_id or not content:
                raise HTTPException(status_code=400, detail="Missing channel_id/content")
            ch = await self._channel(channel_id)
            if not ch or getattr(ch, "guild", None) != guild:
                raise HTTPException(status_code=404, detail="Channel not found")
            await ch.send(content=content)
            return JSONResponse({"ok": True})

        @self.app.post("/api/guilds/{guild_id}/discord/embed")
        async def send_embed(request: Request, guild_id: int):
            guild = await self._require_guild_access(request, guild_id)
            data = await request.json()
            channel_id = self._int(data.get("channel_id", 0))
            title = str(data.get("title", "")).strip()
            description = str(data.get("description", "")).strip()
            color = data.get("color", None)
            footer = str(data.get("footer", "")).strip()
            thumbnail = str(data.get("thumbnail", "")).strip()
            image = str(data.get("image", "")).strip()
            fields = data.get("fields", [])
            if not channel_id or not title:
                raise HTTPException(status_code=400, detail="Missing channel_id/title")
            ch = await self._channel(channel_id)
            if not ch or getattr(ch, "guild", None) != guild:
                raise HTTPException(status_code=404, detail="Channel not found")
            c = None
            try:
                if color:
                    c = int(str(color).replace("#", ""), 16)
            except Exception:
                c = None
            emb = discord.Embed(title=title, description=description or None, color=c)
            if isinstance(fields, list):
                for f in fields[:25]:
                    try:
                        name = str(f.get("name", "")).strip()
                        value = str(f.get("value", "")).strip()
                        inline = bool(f.get("inline", False))
                        if name and value:
                            emb.add_field(name=name, value=value, inline=inline)
                    except Exception:
                        pass
            if footer:
                emb.set_footer(text=footer)
            if thumbnail:
                emb.set_thumbnail(url=thumbnail)
            if image:
                emb.set_image(url=image)
            await ch.send(embed=emb)
            return JSONResponse({"ok": True})

        @self.app.post("/api/guilds/{guild_id}/moderation/timeout")
        async def mod_timeout(request: Request, guild_id: int):
            guild = await self._require_guild_access(request, guild_id)
            data = await request.json()
            user_id = self._int(data.get("user_id", 0))
            minutes = self._int(data.get("minutes", 0))
            moderator_id = self._int(data.get("moderator_id", 0))
            reason = str(data.get("reason", "")).strip() or None
            if not user_id:
                raise HTTPException(status_code=404, detail="User not found")
            member = guild.get_member(user_id)
            if not member:
                raise HTTPException(status_code=404, detail="Member not found")
            moderator = guild.get_member(moderator_id) if moderator_id else None
            if moderator:
                await self.moderation_service.timeout(guild, moderator, member, minutes, reason)
            else:
                until = discord.utils.utcnow() + timedelta(minutes=minutes)
                if hasattr(member, "timeout"):
                    await member.timeout(until, reason=reason)
                else:
                    await member.edit(timed_out_until=until, reason=reason)
            return JSONResponse({"ok": True})

        @self.app.post("/api/guilds/{guild_id}/moderation/kick")
        async def mod_kick(request: Request, guild_id: int):
            guild = await self._require_guild_access(request, guild_id)
            data = await request.json()
            user_id = self._int(data.get("user_id", 0))
            moderator_id = self._int(data.get("moderator_id", 0))
            reason = str(data.get("reason", "")).strip() or None
            member = guild.get_member(user_id) if user_id else None
            if not member:
                raise HTTPException(status_code=404, detail="Member not found")
            moderator = guild.get_member(moderator_id) if moderator_id else None
            if moderator:
                await self.moderation_service.kick(guild, moderator, member, reason)
            else:
                await member.kick(reason=reason)
            return JSONResponse({"ok": True})

        @self.app.post("/api/guilds/{guild_id}/moderation/ban")
        async def mod_ban(request: Request, guild_id: int):
            guild = await self._require_guild_access(request, guild_id)
            data = await request.json()
            user_id = self._int(data.get("user_id", 0))
            delete_days = self._int(data.get("delete_days", 0))
            moderator_id = self._int(data.get("moderator_id", 0))
            reason = str(data.get("reason", "")).strip() or None
            if not user_id:
                raise HTTPException(status_code=404, detail="User not found")
            user = await self.bot.fetch_user(user_id)
            moderator = guild.get_member(moderator_id) if moderator_id else None
            if moderator:
                await self.moderation_service.ban(guild, moderator, user, delete_days, reason)
            else:
                await guild.ban(user, reason=reason, delete_message_days=max(0, min(7, delete_days)))
            return JSONResponse({"ok": True})

        @self.app.post("/api/guilds/{guild_id}/moderation/purge")
        async def mod_purge(request: Request, guild_id: int):
            guild = await self._require_guild_access(request, guild_id)
            data = await request.json()
            channel_id = self._int(data.get("channel_id", 0))
            amount = self._int(data.get("amount", 0))
            user_id = self._int(data.get("user_id", 0) or 0)
            moderator_id = self._int(data.get("moderator_id", 0))
            ch = await self._channel(channel_id)
            if not isinstance(ch, discord.TextChannel) or ch.guild.id != guild.id:
                raise HTTPException(status_code=404, detail="Channel not found")
            moderator = guild.get_member(moderator_id) if moderator_id else None
            if moderator:
                deleted, _err = await self.moderation_service.purge(guild, moderator, ch, amount, guild.get_member(user_id) if user_id else None)
                return JSONResponse({"ok": True, "deleted": int(deleted)})
            else:
                def check(m: discord.Message):
                    return m.author.id == user_id if user_id else True
                deleted = await ch.purge(limit=max(1, min(100, amount)), check=check, bulk=True)
                return JSONResponse({"ok": True, "deleted": len(deleted)})

        @self.app.post("/api/guilds/{guild_id}/roles/add")
        async def roles_add(request: Request, guild_id: int):
            guild = await self._require_guild_access(request, guild_id)
            data = await request.json()
            user_id = self._int(data.get("user_id", 0))
            role_id = self._int(data.get("role_id", 0))
            member = guild.get_member(user_id)
            role = guild.get_role(role_id)
            if not member or not role:
                raise HTTPException(status_code=404, detail="Member/Role not found")
            await member.add_roles(role, reason="Dashboard")
            return JSONResponse({"ok": True})

        @self.app.post("/api/guilds/{guild_id}/roles/remove")
        async def roles_remove(request: Request, guild_id: int):
            guild = await self._require_guild_access(request, guild_id)
            data = await request.json()
            user_id = self._int(data.get("user_id", 0))
            role_id = self._int(data.get("role_id", 0))
            member = guild.get_member(user_id)
            role = guild.get_role(role_id)
            if not member or not role:
                raise HTTPException(status_code=404, detail="Member/Role not found")
            await member.remove_roles(role, reason="Dashboard")
            return JSONResponse({"ok": True})

        @self.app.post("/api/guilds/{guild_id}/tickets/action")
        async def ticket_action(request: Request, guild_id: int):
            guild = await self._require_guild_access(request, guild_id)
            data = await request.json()
            thread_id = self._int(data.get("thread_id", 0))
            action = str(data.get("action", "")).strip()
            user_id = self._int(data.get("user_id", 0) or 0)
            actor_id = self._int(data.get("actor_id", 0) or 0)
            thread = guild.get_thread(thread_id)
            if not thread:
                fetched = await self.bot.fetch_channel(thread_id)
                thread = fetched if isinstance(fetched, discord.Thread) else None
            if not thread:
                raise HTTPException(status_code=404, detail="Thread not found")
            actor = guild.get_member(actor_id) if actor_id else None
            if not actor:
                raise HTTPException(status_code=404, detail="Actor not found")

            if action == "close":
                ok, err = await self.ticket_service.dashboard_close_ticket(guild, thread, actor, reason=data.get("reason"))
            elif action == "claim":
                ok, err = await self.ticket_service.dashboard_set_claim(guild, thread, actor, claimed=True)
            elif action == "release":
                ok, err = await self.ticket_service.dashboard_set_claim(guild, thread, actor, claimed=False)
            elif action == "add_user":
                if not user_id:
                    raise HTTPException(status_code=400, detail="Missing user_id")
                user = await self.bot.fetch_user(user_id)
                ok, err = await self.ticket_service.dashboard_add_participant(guild, thread, actor, user)
            else:
                raise HTTPException(status_code=400, detail="Invalid action")

            if not ok:
                raise HTTPException(status_code=400, detail=err or "Ticket action failed")
            return JSONResponse({"ok": True})

    def _session_cookie_name(self) -> str:
        return "starry_session"

    def _int(self, value) -> int:
        try:
            return int(value)
        except Exception:
            return 0

    @staticmethod
    def _snowflake(value) -> str:
        try:
            return str(int(value))
        except Exception:
            return str(value or "")

    def _json_safe(self, value):
        if isinstance(value, dict):
            return {str(key): self._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._json_safe(item) for item in value]
        if isinstance(value, int) and not isinstance(value, bool) and abs(value) > 9_007_199_254_740_991:
            return str(value)
        return value

    @staticmethod
    def _session_has_dashboard_access(entry: dict | None) -> bool:
        if not isinstance(entry, dict):
            return False
        try:
            perms = int(entry.get("permissions") or 0)
        except Exception:
            perms = 0
        return bool(entry.get("owner")) or (perms & 0x8) == 0x8

    def _session_guild_entry(self, session: dict, guild_id: int | str) -> dict | None:
        target = self._snowflake(guild_id)
        for entry in session.get("guilds", []):
            if self._snowflake(entry.get("id")) == target:
                return entry
        return None

    @staticmethod
    def _member_has_dashboard_access(guild: discord.Guild | None, user_id: int) -> bool:
        if guild is None:
            return False
        member = guild.get_member(int(user_id))
        if member is None:
            return False
        perms = getattr(member, "guild_permissions", None)
        return bool(
            guild.owner_id == member.id
            or getattr(perms, "administrator", False)
            or getattr(perms, "manage_guild", False)
        )

    @staticmethod
    def _channel_sort_key(channel: discord.abc.GuildChannel):
        return (getattr(channel, "position", 0), getattr(channel, "id", 0))

    def _guild_meta_payload(self, guild: discord.Guild) -> dict:
        channels = []
        for channel in sorted(list(guild.channels), key=self._channel_sort_key):
            category = getattr(channel, "category", None)
            channels.append({
                "id": channel.id,
                "name": channel.name,
                "type": str(channel.type),
                "position": int(getattr(channel, "position", 0)),
                "category_id": getattr(category, "id", None),
                "category_name": getattr(category, "name", None),
                "messageable": isinstance(channel, discord.TextChannel),
                "label": f"#{channel.name}" if hasattr(channel, "name") else str(channel.id),
            })

        threads = []
        for thread in sorted(list(guild.threads), key=lambda item: item.id):
            parent = getattr(thread, "parent", None)
            threads.append({
                "id": thread.id,
                "name": thread.name,
                "parent_id": getattr(parent, "id", None),
                "parent_name": getattr(parent, "name", None),
                "archived": bool(getattr(thread, "archived", False)),
            })

        roles = []
        for role in sorted(list(guild.roles), key=lambda item: item.position, reverse=True):
            if role.is_default():
                continue
            roles.append({
                "id": role.id,
                "name": role.name,
                "position": role.position,
                "managed": role.managed,
                "mentionable": role.mentionable,
                "color": f"#{role.color.value:06x}",
            })

        all_members = sorted(list(guild.members), key=lambda item: item.display_name.casefold())
        members = []
        for member in all_members[:500]:
            try:
                avatar_url = member.display_avatar.url
            except Exception:
                avatar_url = None
            members.append({
                "id": member.id,
                "name": member.name,
                "display_name": member.display_name,
                "bot": member.bot,
                "avatar_url": avatar_url,
            })

        icon_url = None
        try:
            icon_url = guild.icon.url if guild.icon else None
        except Exception:
            icon_url = None

        return {
            "guild": {
                "id": guild.id,
                "name": guild.name,
                "icon_url": icon_url,
                "member_count": guild.member_count,
            },
            "channels": channels,
            "threads": threads,
            "roles": roles,
            "members": members,
            "members_truncated": len(all_members) > 500,
        }

    @staticmethod
    def _default_avatar_url(user_id: int) -> str:
        try:
            index = (int(user_id) >> 22) % 6
        except Exception:
            index = 0
        return f"https://cdn.discordapp.com/embed/avatars/{index}.png"

    def _avatar_url_from_hash(self, user_id: int, avatar_hash: str | None) -> str:
        avatar = str(avatar_hash or "").strip()
        if not avatar:
            return self._default_avatar_url(user_id)
        ext = "gif" if avatar.startswith("a_") else "webp"
        return f"https://cdn.discordapp.com/avatars/{int(user_id)}/{avatar}.{ext}?size=128"

    async def _user_brief(self, user_id: int) -> dict:
        uid = int(user_id)
        user = self.bot.get_user(uid)
        if user is None:
            for guild in self.bot.guilds:
                member = guild.get_member(uid)
                if member is not None:
                    user = member
                    break
        if user is None:
            try:
                user = await self.bot.fetch_user(uid)
            except Exception:
                user = None

        username = None
        display_name = f"User {uid}"
        avatar_url = self._default_avatar_url(uid)

        if user is not None:
            username = str(getattr(user, "name", "") or "") or None
            display_name = str(
                getattr(user, "display_name", None)
                or getattr(user, "global_name", None)
                or getattr(user, "name", None)
                or display_name
            )
            try:
                avatar_url = str(user.display_avatar.replace(size=128, format="webp").url)
            except Exception:
                try:
                    avatar_url = str(user.display_avatar.url)
                except Exception:
                    avatar_url = self._default_avatar_url(uid)

        return {
            "id": uid,
            "username": username,
            "display_name": display_name,
            "avatar_url": avatar_url,
        }

    def dashboard_port(self) -> int:
        try:
            return int(self.settings.get("bot.dashboard.port", 8787) or 8787)
        except Exception:
            return 8787

    def dashboard_host_raw(self) -> str:
        return str(self.settings.get("bot.dashboard.host", "0.0.0.0") or "0.0.0.0").strip()

    def dashboard_bind_host(self) -> str:
        raw = self.dashboard_host_raw()
        if not raw:
            return "0.0.0.0"
        if "://" in raw:
            parsed = urlparse(raw)
            host = parsed.hostname or ""
            if host and host not in {"0.0.0.0", "127.0.0.1", "localhost"}:
                return "0.0.0.0"
            return host or "0.0.0.0"
        return raw

    def dashboard_public_base_url(self) -> str:
        redirect = str(self.settings.get("bot.dashboard.redirect_uri", "") or "").strip()
        if redirect:
            parsed = urlparse(redirect)
            if parsed.scheme and parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}"

        raw = self.dashboard_host_raw()
        port = self.dashboard_port()
        if "://" in raw:
            parsed = urlparse(raw)
            scheme = parsed.scheme or "http"
            host = parsed.hostname or "127.0.0.1"
            if parsed.port:
                return f"{scheme}://{host}:{parsed.port}"
            return f"{scheme}://{host}:{port}"

        host = raw or "127.0.0.1"
        if host == "0.0.0.0":
            host = "127.0.0.1"
        return f"http://{host}:{port}"

    def _selector_type(self, meta: SettingMeta) -> str | None:
        leaf = str(meta.leaf_name or "")
        if leaf.endswith("_channel_id") or leaf.endswith("_channel_ids"):
            return "channel"
        if leaf.endswith("_thread_id") or leaf.endswith("_thread_ids"):
            return "thread"
        if leaf.endswith("_role_id") or leaf.endswith("_role_ids"):
            return "role"
        if leaf.endswith("_user_id") or leaf.endswith("_user_ids"):
            return "user"
        return None

    def _setup_raw_value(self, value) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        if value is None:
            return ""
        return str(value)

    def _serialize_setup_setting(self, guild_id: int, meta: SettingMeta) -> dict:
        current_value = self.setup_service.current_value(int(guild_id), meta)
        global_value = self.setup_service.global_value(meta)
        sensitive = bool(meta.sensitive)
        return {
            "module_key": meta.module_key,
            "relative_path": meta.relative_path,
            "full_path": meta.full_path,
            "leaf_name": meta.leaf_name,
            "kind": meta.kind,
            "element_kind": meta.element_kind,
            "type_label": meta.type_label,
            "selector_type": self._selector_type(meta),
            "sensitive": sensitive,
            "has_override": bool(self.setup_service.has_override(int(guild_id), meta.full_path)),
            "example": self.setup_service.example_value(meta),
            "current_display": self.setup_service.format_value(current_value, meta, limit=400),
            "global_display": self.setup_service.format_value(global_value, meta, limit=400),
            "current_value": None if sensitive else self._json_safe(current_value),
            "global_value": None if sensitive else self._json_safe(global_value),
        }

    def _serialize_setup_module(self, guild_id: int, module_key: str, *, include_settings: bool) -> dict:
        info = self.setup_service._module_info(module_key)
        metas = self.setup_service.setting_metas(module_key, guild_id=int(guild_id))
        payload = {
            "key": module_key,
            "label": info["label"],
            "emoji": info["emoji"],
            "aliases": list(info["aliases"]),
            "settings_total": len(metas),
            "override_total": sum(1 for meta in metas if self.setup_service.has_override(int(guild_id), meta.full_path)),
        }
        if include_settings:
            payload["settings"] = [self._serialize_setup_setting(int(guild_id), meta) for meta in metas]
        return payload

    def _require_setup_meta(self, guild_id: int, module_key: str, setting: str | None) -> tuple[str, SettingMeta]:
        resolved = self.setup_service.resolve_module_key(module_key)
        if not resolved:
            raise HTTPException(status_code=404, detail="Module not found")
        meta = self.setup_service.resolve_setting_meta(resolved, setting, guild_id=int(guild_id))
        if meta is None:
            raise HTTPException(status_code=404, detail="Setting not found")
        return resolved, meta

    def _discord_oauth_url(self) -> str:
        client_id = str(self.settings.get("bot.dashboard.client_id", "") or "").strip()
        redirect = str(self.settings.get("bot.dashboard.redirect_uri", "") or "").strip()
        if not client_id or not redirect:
            raise HTTPException(status_code=500, detail="OAuth not configured")
        params = {
            "client_id": client_id,
            "redirect_uri": redirect,
            "response_type": "code",
            "scope": "identify guilds",
        }
        return "https://discord.com/api/oauth2/authorize?" + urlencode(params)

    async def _exchange_code(self, code: str) -> dict:
        client_id = str(self.settings.get("bot.dashboard.client_id", "") or "").strip()
        client_secret = str(self.settings.get("bot.dashboard.client_secret", "") or "").strip()
        redirect = str(self.settings.get("bot.dashboard.redirect_uri", "") or "").strip()
        if not client_id or not client_secret or not redirect:
            raise HTTPException(status_code=500, detail="OAuth not configured")
        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect,
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post("https://discord.com/api/oauth2/token", data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        if resp.status_code >= 400:
            raise HTTPException(status_code=400, detail=f"OAuth token failed: {resp.text}")
        return resp.json()

    async def _fetch_user(self, access_token: str) -> dict:
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get("https://discord.com/api/users/@me", headers=headers)
        if resp.status_code >= 400:
            raise HTTPException(status_code=400, detail="Failed to fetch user")
        return resp.json()

    async def _fetch_guilds(self, access_token: str) -> list:
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get("https://discord.com/api/users/@me/guilds", headers=headers)
        if resp.status_code >= 400:
            raise HTTPException(status_code=400, detail="Failed to fetch guilds")
        data = resp.json()
        return data if isinstance(data, list) else []

    async def _require_session(self, request: Request) -> dict:
        session_id = request.cookies.get(self._session_cookie_name())
        if not session_id:
            raise HTTPException(status_code=401, detail="Missing session")
        row = await self.db.get_dashboard_session(session_id)
        if not row:
            raise HTTPException(status_code=401, detail="Invalid session")
        expires_at = int(row[6])
        if expires_at <= int(time.time()):
            await self.db.delete_dashboard_session(session_id)
            raise HTTPException(status_code=401, detail="Session expired")
        return {
            "session_id": row[0],
            "user_id": int(row[1]),
            "username": row[2],
            "avatar": row[3],
            "access_token": row[4],
            "refresh_token": row[5],
            "expires_at": int(row[6]),
            "guilds": json.loads(row[7] or "[]"),
        }

    async def _require_socket_session(self, websocket: WebSocket) -> dict:
        session_id = websocket.cookies.get(self._session_cookie_name())
        if not session_id:
            await websocket.close(code=4401)
            raise HTTPException(status_code=401, detail="Missing session")
        row = await self.db.get_dashboard_session(session_id)
        if not row:
            await websocket.close(code=4401)
            raise HTTPException(status_code=401, detail="Invalid session")
        expires_at = int(row[6])
        if expires_at <= int(time.time()):
            await self.db.delete_dashboard_session(session_id)
            await websocket.close(code=4401)
            raise HTTPException(status_code=401, detail="Session expired")
        return {
            "session_id": row[0],
            "user_id": int(row[1]),
            "username": row[2],
            "avatar": row[3],
            "access_token": row[4],
            "refresh_token": row[5],
            "expires_at": int(row[6]),
            "guilds": json.loads(row[7] or "[]"),
        }

    def _session_payload(self, session: dict) -> dict:
        user_id = int(session["user_id"])
        return {
            "user": {
                "id": self._snowflake(user_id),
                "username": session["username"],
                "avatar": session.get("avatar") or None,
                "avatar_url": self._avatar_url_from_hash(user_id, session.get("avatar")),
                "display_name": session["username"],
            },
            "guilds": self._accessible_guilds(session),
        }

    def _accessible_guilds(self, session: dict) -> list[dict]:
        out = []
        seen: set[int] = set()
        user_id = int(session["user_id"])
        candidate_ids: list[int] = []

        for entry in session.get("guilds", []):
            try:
                candidate_ids.append(int(entry.get("id")))
            except Exception:
                continue

        for guild in self.bot.guilds:
            if self._member_has_dashboard_access(guild, user_id):
                candidate_ids.append(int(guild.id))

        for gid in candidate_ids:
            if gid in seen:
                continue
            seen.add(gid)
            bot_guild = self.bot.get_guild(gid)
            if not bot_guild:
                continue
            session_entry = self._session_guild_entry(session, gid)
            session_allowed = self._session_has_dashboard_access(session_entry)
            cached_allowed = self._member_has_dashboard_access(bot_guild, user_id)
            if not (session_allowed or cached_allowed):
                continue

            perms = 8 if cached_allowed else int((session_entry or {}).get("permissions") or 0)
            is_owner = bool((session_entry or {}).get("owner")) or bot_guild.owner_id == user_id
            icon_hash = (session_entry or {}).get("icon")
            icon_url = None
            if icon_hash:
                icon_url = f"https://cdn.discordapp.com/icons/{gid}/{icon_hash}.webp?size=128"
            elif getattr(bot_guild, "icon", None):
                try:
                    icon_url = str(bot_guild.icon.url)
                except Exception:
                    icon_url = None
            out.append({
                "id": self._snowflake(gid),
                "name": (session_entry or {}).get("name") or bot_guild.name,
                "icon": icon_hash,
                "icon_url": icon_url,
                "owner": is_owner,
                "permissions": perms,
                "bot_in_guild": True,
            })
        return out

    async def _require_guild_access(self, request: Request, guild_id: int) -> discord.Guild:
        session = await self._require_session(request)
        gid = int(guild_id)
        guild = self.bot.get_guild(gid)
        if not guild:
            raise HTTPException(status_code=404, detail="Guild not found")
        session_entry = self._session_guild_entry(session, gid)
        session_allowed = self._session_has_dashboard_access(session_entry)
        cached_allowed = self._member_has_dashboard_access(guild, int(session["user_id"]))
        if not (session_allowed or cached_allowed):
            raise HTTPException(status_code=403, detail="Missing permissions")
        return guild

    async def _channel(self, channel_id: int):
        ch = self.bot.get_channel(int(channel_id))
        if ch:
            return ch
        try:
            return await self.bot.fetch_channel(int(channel_id))
        except Exception:
            return None

    async def start(self):
        host = self.dashboard_bind_host()
        port = self.dashboard_port()
        config = uvicorn.Config(self.app, host=host, port=port, log_level="warning")
        self._server = uvicorn.Server(config)
        loop = asyncio.get_running_loop()
        self._task = loop.create_task(self._serve())
        await asyncio.sleep(0)
        if self._task.done():
            exc = self._task.exception()
            if exc:
                raise exc

    async def _serve(self):
        try:
            await self._server.serve()
        except SystemExit as exc:
            raise RuntimeError(f"Dashboard-Start fehlgeschlagen: {exc}") from exc

    async def stop(self):
        if self._server:
            self._server.should_exit = True
        if self._task:
            try:
                await self._task
            except RuntimeError:
                pass
