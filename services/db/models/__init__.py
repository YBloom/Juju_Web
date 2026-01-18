"""Aggregate exports for SQLModel tables."""

from .base import (
    GroupType,
    HLQTicketStatus,
    ItemDirection,
    PlaySource,
    SendQueueStatus,
    SoftDelete,
    SubscriptionFrequency,
    SubscriptionTargetKind,
    TimeStamped,
    TradeStatus,
    TradeType,
    utcnow,
)
from .group import Group, Membership
from .hlq import HLQEvent, HLQTicket
from .inventory import UserInventory, TicketStatus, TicketSource
from .marketplace import MarketplaceListing, ListingItem, ItemType
from .observability import ErrorLog, Metric, SendQueue
from .play import Play, PlayAlias, PlaySnapshot, PlaySourceLink
from .subscription import Subscription, SubscriptionOption, SubscriptionTarget
from .user import User

# Import SaojuCache for database initialization
from services.hulaquan.tables import SaojuCache

__all__ = [
    "ErrorLog",
    "Group",
    "GroupType",
    "HLQEvent",
    "HLQTicket",
    "ItemDirection",
    "ItemType",
    "ListingItem",
    "MarketplaceListing",
    "Metric",
    "Membership",
    "Play",
    "PlayAlias",
    "PlaySnapshot",
    "PlaySource",
    "PlaySourceLink",
    "SaojuCache",
    "SendQueue",
    "SendQueueStatus",
    "SoftDelete",
    "Subscription",
    "SubscriptionFrequency",
    "SubscriptionOption",
    "SubscriptionTarget",
    "SubscriptionTargetKind",
    "TicketSource",
    "TicketStatus",
    "TimeStamped",
    "TradeStatus",
    "TradeType",
    "User",
    "UserInventory",
    "utcnow",
]
