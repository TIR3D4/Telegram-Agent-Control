"""Shared, deny-by-default policy for HTTP, MCP and durable execution."""

from contextvars import ContextVar
from datetime import timezone
from fastapi import HTTPException
from sqlalchemy import select
from .config import settings
from .registry import registry

request_context: ContextVar[dict] = ContextVar("tac_request", default={})
READ_METHODS = frozenset(
    {
        "getMe",
        "getChat",
        "getChatMember",
        "getChatMemberCount",
        "getChatAdministrators",
        "getStickerSet",
        "getCustomEmojiStickers",
    }
)
POST_METHODS = frozenset(
    {
        "sendMessage",
        "sendPhoto",
        "sendVideo",
        "sendAnimation",
        "sendAudio",
        "sendVoice",
        "sendVideoNote",
        "sendDocument",
        "sendMediaGroup",
        "sendRichMessage",
        "sendPoll",
        "sendLocation",
        "sendVenue",
        "sendContact",
        "sendSticker",
        "sendDice",
        "editMessageText",
        "editMessageCaption",
        "editMessageMedia",
        "editMessageReplyMarkup",
        "editMessageLiveLocation",
        "stopMessageLiveLocation",
        "stopPoll",
        "deleteMessage",
        "deleteMessages",
        "pinChatMessage",
        "unpinChatMessage",
        "unpinAllChatMessages",
        "copyMessage",
        "copyMessages",
        "forwardMessage",
        "forwardMessages",
    }
)
READ_SCOPES = frozenset(
    {
        "system:read",
        "telegram:read",
        "posts:read",
        "media:read",
        "workflows:read",
        "emoji:read",
        "logs:read",
        "metrics:read",
        "database:read",
        "settings:read",
    }
)
OPERATE_SCOPES = READ_SCOPES | {
    "posts:write",
    "media:write",
    "keyboards:write",
    "workflows:write",
    "emoji:write",
    "maintenance:request",
}
PRESETS = {"READ": READ_SCOPES, "OPERATE": OPERATE_SCOPES, "ADMIN": OPERATE_SCOPES | {"telegram:admin"}}


class Identity(str):
    preset: str
    scopes: frozenset[str]
    chats: frozenset[str]
    methods: frozenset[str]
    human: bool

    def __new__(cls, id, preset="OPERATE", scopes=None, chats=None, methods=None, human=False):
        obj = super().__new__(cls, id)
        obj.preset = preset
        obj.scopes = frozenset(scopes if scopes is not None else PRESETS[preset])
        obj.chats = frozenset(str(x).lower() for x in (chats if chats is not None else settings().chats))
        obj.methods = frozenset(
            methods if methods is not None else READ_METHODS | (POST_METHODS if preset != "READ" else set())
        )
        obj.human = human
        return obj


def identity(actor):
    if isinstance(actor, Identity):
        return actor
    if actor == "owner":
        return Identity("owner", "ADMIN", human=True)
    if actor in {"agent", "reader"}:
        if not settings().legacy_agent_keys_enabled:
            raise HTTPException(403, "Legacy agent credentials disabled")
        return Identity(actor, "READ" if actor == "reader" else "OPERATE")
    raise HTTPException(403, "Unknown execution principal")


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def grant_identity(grant, scopes=None):
    from .db import now

    if grant.revoked_at or utc(grant.expires_at) <= now():
        raise HTTPException(401, "Agent grant expired or revoked")
    allowed = set(grant.scopes) & PRESETS[grant.preset]
    if scopes is not None:
        allowed &= set(scopes)
    return Identity("agent:" + grant.id, grant.preset, allowed, grant.chats, grant.methods)


def execution_identity(db, actor):
    from .db import AgentGrant

    if actor.startswith("agent:"):
        grant = db.get(AgentGrant, actor[6:])
        if not grant:
            raise HTTPException(403, "Execution grant removed")
        return grant_identity(grant)
    return identity(actor)


def require(actor, scope):
    who = identity(actor)
    if not who.human and scope not in who.scopes:
        raise HTTPException(403, "Required scope: " + scope)
    return who


def targets(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in {"chat_id", "from_chat_id", "sender_chat_id"}:
                yield str(value).lower()
            elif isinstance(value, (dict, list)):
                yield from targets(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from targets(item)


def authorize_method(actor, method, payload):
    who = identity(actor)
    if method not in registry()["methods"]:
        raise ValueError("Unknown Telegram method")
    if not who.human:
        if method not in who.methods:
            raise HTTPException(403, "Telegram method is not granted")
        scope = (
            "telegram:read"
            if registry()["methods"][method]["effect"] == "read"
            else ("posts:write" if method in POST_METHODS else "telegram:admin")
        )
        require(who, scope)
        # Inline message IDs do not identify a destination that can be authorized.
        if "inline_message_id" in payload or method == "answerCallbackQuery":
            raise HTTPException(403, "Inline message control requires human owner")
    for target in targets(payload):
        if target not in settings().chats or (not who.human and target not in who.chats):
            raise HTTPException(403, "Destination is outside the granted channel policy")
    return who


def visible(actor, obj):
    who = identity(actor)
    if who.human:
        return True
    if getattr(obj, "actor", None) == "catalog":
        return "emoji:read" in who.scopes
    if getattr(obj, "actor", None) != str(who):
        return False
    payloads = [getattr(obj, "payload", {})]
    payloads += [s.get("payload", {}) for s in getattr(obj, "steps", []) or []]
    return all(t in who.chats and t in settings().chats for p in payloads for t in targets(p))


def resource(actor, obj):
    if not visible(actor, obj):
        raise HTTPException(404, "Resource not found")
    return obj


def owned_query(actor, cls):
    who = identity(actor)
    query = select(cls)
    if not who.human:
        query = query.where(cls.actor == str(who))
    return query


def authorize_steps(actor, steps, trigger=None):
    require(actor, "workflows:write")
    for step in steps:
        authorize_method(actor, step["method"], step.get("payload", {}))
    if trigger and trigger.get("type") == "update":
        authorize_method(actor, "getChat", {"chat_id": trigger.get("chat_id")})
