"""store messages as parts

Moves messages from the Anthropic API's format (`content`) to our own (`parts`), adds `provider`,
`model` and `raw`, and gives tool results their own "tool" role.

The conversions are written out here rather than imported from the app, so this migration keeps
working however the app's code changes later.

Revision ID: 6657cea5c2a8
Revises: 83e55a07969a
Create Date: 2026-11-14 14:06:21.495521

"""

import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "6657cea5c2a8"
down_revision: str | Sequence[str] | None = "83e55a07969a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_ROLES = "role IN ('user', 'assistant')"
NEW_ROLES = "role IN ('user', 'assistant', 'tool')"


def _part_from_block(block: dict[str, Any]) -> dict[str, Any]:
    match block["type"]:
        case "text":
            return {"type": "text", "text": block["text"]}
        case "tool_use":
            return {
                "type": "tool_call",
                "id": block["id"],
                "name": block["name"],
                "arguments": block["input"],
            }
        case "tool_result":
            content = block.get("content", "")
            return {
                "type": "tool_result",
                "call_id": block["tool_use_id"],
                "content": content if isinstance(content, str) else json.dumps(content),
                "is_error": block.get("is_error", False),
            }
        case "thinking" | "redacted_thinking":
            return {
                "type": "reasoning",
                "provider": "anthropic",
                "text": block.get("thinking"),
                "opaque": block,
            }
        case _:
            return {"type": "provider", "provider": "anthropic", "data": block}


def _block_from_part(part: dict[str, Any]) -> dict[str, Any] | None:
    match part["type"]:
        case "text":
            return {"type": "text", "text": part["text"]}
        case "tool_call":
            return {
                "type": "tool_use",
                "id": part["id"],
                "name": part["name"],
                "input": part["arguments"],
            }
        case "tool_result":
            return {
                "type": "tool_result",
                "tool_use_id": part["call_id"],
                "content": part["content"],
                "is_error": part["is_error"],
            }
        case "reasoning" if part["provider"] == "anthropic":
            return part["opaque"]
        case "provider" if part["provider"] == "anthropic":
            return part["data"]
        case _:
            return None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("messages", sa.Column("parts", JSONB(), nullable=True))
    op.add_column("messages", sa.Column("provider", sa.String(), nullable=True))
    op.add_column("messages", sa.Column("model", sa.String(), nullable=True))
    op.add_column("messages", sa.Column("raw", JSONB(), nullable=True))
    op.drop_constraint(op.f("ck_messages_role"), "messages", type_="check")
    op.create_check_constraint(op.f("ck_messages_role"), "messages", NEW_ROLES)

    update = sa.text(
        "UPDATE messages SET role = :role, parts = :parts, provider = :provider, raw = :raw "
        "WHERE id = :id"
    ).bindparams(sa.bindparam("parts", type_=JSONB), sa.bindparam("raw", type_=JSONB))
    bind = op.get_bind()
    for id, role, content in bind.execute(sa.text("SELECT id, role, content FROM messages")):
        provider = None
        raw = None
        if isinstance(content, str):
            parts = [{"type": "text", "text": content}]
        else:
            parts = [_part_from_block(block) for block in content]
            if role == "user":
                # A user message holding blocks was always tool results.
                role = "tool"
            else:
                raw = {"content": content}
                if any(part["type"] == "reasoning" for part in parts):
                    provider = "anthropic"
        bind.execute(
            update, {"id": id, "role": role, "parts": parts, "provider": provider, "raw": raw}
        )

    op.alter_column("messages", "parts", nullable=False)
    op.drop_column("messages", "content")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column("messages", sa.Column("content", JSONB(), nullable=True))

    update = sa.text("UPDATE messages SET role = :role, content = :content WHERE id = :id")
    update = update.bindparams(sa.bindparam("content", type_=JSONB))
    bind = op.get_bind()
    for id, role, parts in bind.execute(sa.text("SELECT id, role, parts FROM messages")):
        if role == "user":
            content = "".join(part["text"] for part in parts if part["type"] == "text")
        else:
            content = [block for part in parts if (block := _block_from_part(part))]
            role = "user" if role == "tool" else role
        bind.execute(update, {"id": id, "role": role, "content": content})

    op.alter_column("messages", "content", nullable=False)
    op.drop_constraint(op.f("ck_messages_role"), "messages", type_="check")
    op.create_check_constraint(op.f("ck_messages_role"), "messages", OLD_ROLES)
    op.drop_column("messages", "raw")
    op.drop_column("messages", "model")
    op.drop_column("messages", "provider")
    op.drop_column("messages", "parts")
