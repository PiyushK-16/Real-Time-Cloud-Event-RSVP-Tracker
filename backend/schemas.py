"""Request validation (Pydantic). Invalid input never reaches the database."""
from datetime import date, datetime, time
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    role: Literal["attendee", "organizer"] = "attendee"  # admin can never self-register


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


def _check_link(v):
    if v and not (v.startswith("https://") or v.startswith("http://")):
        raise ValueError("online_link must start with http:// or https://")
    return v or None


class EventIn(BaseModel):
    event_name: str = Field(min_length=3, max_length=150)
    description: str = Field(default="", max_length=5000)
    event_type: str = Field(default="general", max_length=50)
    event_date: date
    start_time: time
    end_time: time
    venue: Optional[str] = Field(default=None, max_length=255)
    online_link: Optional[str] = Field(default=None, max_length=500)
    maximum_capacity: int = Field(ge=1, le=100000)
    registration_deadline: Optional[datetime] = None
    publish: bool = True

    _link = field_validator("online_link")(_check_link)


class EventUpdate(BaseModel):
    event_name: Optional[str] = Field(default=None, min_length=3, max_length=150)
    description: Optional[str] = Field(default=None, max_length=5000)
    event_type: Optional[str] = Field(default=None, max_length=50)
    event_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    venue: Optional[str] = Field(default=None, max_length=255)
    online_link: Optional[str] = Field(default=None, max_length=500)
    maximum_capacity: Optional[int] = Field(default=None, ge=1, le=100000)
    registration_deadline: Optional[datetime] = None

    _link = field_validator("online_link")(_check_link)


class RSVPIn(BaseModel):
    status: Literal["GOING", "MAYBE", "NOT_GOING"]


class AnnouncementIn(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    message: str = Field(min_length=1, max_length=2000)
    category: Literal["VENUE_UPDATED", "TIMING_CHANGED", "REMINDER", "EVENT_CANCELLED",
                      "IMPORTANT_INSTRUCTIONS", "GENERAL"] = "GENERAL"


class InviteIn(BaseModel):
    emails: list[EmailStr] = Field(min_length=1, max_length=500)
