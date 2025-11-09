# services/db/models/group.py
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship

from .base import TimeStamped, SoftDelete, GroupType

class Group(SQLModel, TimeStamped, SoftDelete, table=True):
    group_id: str = Field(primary_key=True)
    name: Optional[str] = None
    group_type: GroupType = Field(default=GroupType.BROADCAST)
    active: bool = Field(default=True)
    members: List["Membership"] = Relationship(back_populates="group")

class Membership(SQLModel, TimeStamped, table=True):
    """用户-群 关系；多对多中间表。"""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.user_id", index=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)

    is_admin: bool = Field(default=False)
    receive_broadcast: bool = Field(default=True)

    user: "User" = Relationship(back_populates="memberships")
    group: "Group" = Relationship(back_populates="members")
