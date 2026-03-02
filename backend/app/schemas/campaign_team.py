"""
Schemas for Campaign Team routes.
"""
from pydantic import BaseModel
from typing import Optional


class AlertAssignRequest(BaseModel):
    assignee: Optional[str] = None
    note: Optional[str] = None
