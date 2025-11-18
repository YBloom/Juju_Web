#!/usr/bin/env python3
"""Import legacy JSON data into the SQLModel schema.

Usage:
    python scripts/import_v0_json.py --data-root data/data_manager --db-path data/musicalbot.db

The script ingests Users/Groups/Subscriptions and Alias/Play mappings from the
JSON files that the legacy DataManager classes produced. It is intentionally
idempotent for empty databases—if rows already exist, the script will skip them
rather than overwriting.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from sqlmodel import Session, select

from services.db.init import init_db
from services.db.models import (
    Group,
    Play,
    PlayAlias,
    PlaySource,
    PlaySourceLink,
    Subscription,
    SubscriptionFrequency,
    SubscriptionOption,
    SubscriptionTarget,
    SubscriptionTargetKind,
    User,
    utcnow,
)

LEGACY_USER_FILE = "UsersManager.json"
LEGACY_ALIAS_FILE = "alias.json"


@dataclass
class ImportStats:
    users: int = 0
    groups: int = 0
    subscriptions: int = 0
    aliases: int = 0
    plays: int = 0

    def as_dict(self) -> Dict[str, int]:
        return {
            "users": self.users,
            "groups": self.groups,
            "subscriptions": self.subscriptions,
            "aliases": self.aliases,
            "plays": self.plays,
        }


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Failed to parse {path}: {exc}") from exc


def parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def normalize(value: Optional[str]) -> str:
    if not value:
        return ""
    return value.strip().lower()


class LegacyImporter:
    def __init__(self, data_root: Path, session: Session):
        self.data_root = data_root
        self.session = session
        self.stats = ImportStats()
        self._play_cache: Dict[str, Play] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self) -> ImportStats:
        self._import_users_and_groups()
        self._import_aliases()
        return self.stats

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _import_users_and_groups(self) -> None:
        payload = load_json(self.data_root / LEGACY_USER_FILE)
        if not payload:
            print(f"[import] Skip users: {LEGACY_USER_FILE} not found or empty")
            return

        users = payload.get("users", {})
        groups = payload.get("groups", {})
        subscribe_defaults = payload.get("subscribe", {})

        for user_id in payload.get("users_list", users.keys()):
            record = users.get(str(user_id), {})
            created_at = parse_dt(record.get("create_time")) or utcnow()
            user = User(
                user_id=str(user_id),
                nickname=record.get("nickname"),
                active=bool(record.get("activate", True)),
                transactions_success=int(record.get("transactions_success", 0)),
                trust_score=int(record.get("trust_score", 0)),
                extra_json=record or None,
                created_at=created_at,
                updated_at=created_at,
            )
            self.session.merge(user)
            self.stats.users += 1
            self.stats.subscriptions += self._import_subscriptions_for_user(
                user.user_id,
                record.get("subscribe") or subscribe_defaults,
            )

        for group_id in payload.get("groups_list", groups.keys()):
            record = groups.get(str(group_id), {})
            created_at = parse_dt(record.get("create_time")) or utcnow()
            group = Group(
                group_id=str(group_id),
                name=record.get("name"),
                active=bool(record.get("activate", True)),
                extra_json=record or None,
                created_at=created_at,
                updated_at=created_at,
            )
            self.session.merge(group)
            self.stats.groups += 1

    def _import_subscriptions_for_user(self, user_id: str, payload: Dict[str, Any]) -> int:
        created = 0
        created += self._import_subscription_list(
            user_id,
            payload.get("subscribe_tickets", []),
            SubscriptionTargetKind.PLAY,
        )
        created += self._import_subscription_list(
            user_id,
            payload.get("subscribe_events", []),
            SubscriptionTargetKind.EVENT,
        )
        created += self._import_subscription_list(
            user_id,
            payload.get("subscribe_actors", []),
            SubscriptionTargetKind.ACTOR,
        )
        return created

    def _import_subscription_list(
        self,
        user_id: str,
        entries: Iterable[Any],
        kind: SubscriptionTargetKind,
    ) -> int:
        created = 0
        for entry in entries or []:
            target_id, name, city, flags = self._extract_subscription_entry(entry)
            if not target_id and not name:
                continue
            subscription = Subscription(user_id=user_id)
            self.session.add(subscription)
            self.session.flush()
            target = SubscriptionTarget(
                subscription_id=subscription.id,
                kind=kind,
                target_id=target_id,
                name=name,
                city_filter=city,
                flags=flags or None,
            )
            option = SubscriptionOption(
                subscription_id=subscription.id,
                mute=bool(flags.get("mute", False)) if isinstance(flags, dict) else False,
                freq=SubscriptionFrequency.REALTIME,
                allow_broadcast=True,
                last_notified_at=parse_dt(flags.get("subscribe_time")) if isinstance(flags, dict) else None,
            )
            self.session.add(target)
            self.session.add(option)
            created += 1
        return created

    @staticmethod
    def _extract_subscription_entry(entry: Any) -> tuple[str, Optional[str], Optional[str], Dict[str, Any]]:
        if isinstance(entry, dict):
            value = entry.get("id") or entry.get("event_id") or entry.get("actor")
            if not value:
                value = entry.get("name") or entry.get("keyword")
            target_id = str(value) if value is not None else None
            city = entry.get("city") or entry.get("city_filter")
            name = entry.get("name")
            flags = {
                k: v
                for k, v in entry.items()
                if k
                not in {"id", "event_id", "actor", "name", "city", "city_filter"}
            }
            return target_id, name, city, flags
        return str(entry), None, None, {}

    def _import_aliases(self) -> None:
        payload = load_json(self.data_root / LEGACY_ALIAS_FILE)
        if not payload:
            print(f"[import] Skip aliases: {LEGACY_ALIAS_FILE} not found or empty")
            return

        alias_to_event = payload.get("alias_to_event", {})
        event_to_names = payload.get("event_to_names", {})
        no_response = payload.get("no_response", {})

        for alias, event_id in alias_to_event.items():
            play = self._get_or_create_play(str(event_id), event_to_names.get(str(event_id), []))
            self.stats.aliases += self._create_alias(
                play,
                alias,
                source="alias",
                weight=100,
                no_response=self._lookup_no_response(no_response, alias),
            )

        for event_id, names in event_to_names.items():
            play = self._get_or_create_play(str(event_id), names)
            for name in names:
                self.stats.aliases += self._create_alias(
                    play,
                    name,
                    source="search_name",
                    weight=50,
                    no_response=0,
                )

    def _get_or_create_play(self, legacy_event_id: str, names: Iterable[str]) -> Play:
        if legacy_event_id in self._play_cache:
            return self._play_cache[legacy_event_id]

        primary_name = next((n for n in names if n), f"Legacy-{legacy_event_id}")
        play = Play(
            name=primary_name,
            name_norm=normalize(primary_name),
            note=f"Imported from legacy alias {legacy_event_id}",
        )
        self.session.add(play)
        self.session.flush()
        link = PlaySourceLink(
            play_id=play.id,
            source=PlaySource.LEGACY,
            source_id=legacy_event_id,
            title_at_source=primary_name,
        )
        self.session.add(link)
        self._play_cache[legacy_event_id] = play
        self.stats.plays += 1
        return play

    def _create_alias(
        self,
        play: Play,
        alias: str,
        *,
        source: str,
        weight: int,
        no_response: int,
    ) -> int:
        alias_norm = normalize(alias)
        if not alias_norm:
            return 0
        existing = self.session.exec(
            select(PlayAlias).where(
                PlayAlias.play_id == play.id,
                PlayAlias.alias_norm == alias_norm,
            )
        ).first()
        if existing:
            return 0
        self.session.add(
            PlayAlias(
                play_id=play.id,
                alias=alias,
                alias_norm=alias_norm,
                source=source,
                weight=weight,
                no_response_count=no_response,
            )
        )
        return 1

    @staticmethod
    def _lookup_no_response(
        no_response_map: Dict[str, Any],
        alias: str,
    ) -> int:
        prefix = f"{alias}:"
        values = [int(v) for k, v in no_response_map.items() if k.startswith(prefix)]
        return max(values) if values else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import legacy JSON data into SQLite")
    parser.add_argument(
        "--data-root",
        default="data/data_manager",
        help="Directory that contains legacy JSON files",
    )
    parser.add_argument(
        "--db-path",
        default="data/musicalbot.db",
        help="SQLite file to migrate into",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load data but roll back the transaction",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_root = Path(args.data_root)
    if not data_root.exists():
        raise SystemExit(f"Data directory {data_root} does not exist")

    engine = init_db(args.db_path)
    with Session(engine) as session:
        importer = LegacyImporter(data_root, session)
        stats = importer.run()
        if args.dry_run:
            session.rollback()
            print("[import] Dry-run complete; no data committed.")
        else:
            session.commit()
            print("[import] Migration finished:", stats.as_dict())


if __name__ == "__main__":
    main()
