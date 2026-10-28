from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator

Role = Literal["employee", "manager"]
Status = Literal["Planned", "In Progress", "Completed"]
Priority = Literal["Low", "Medium", "High", "Urgent"]
class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2,max_length=60)
    email: EmailStr
    password: str = Field(min_length=8,max_length=128)
    focus_goal: str = Field(default="",max_length=120)
    @field_validator("full_name")
    @classmethod
    def trim_name(cls,v):
        v=v.strip()
        if not v: raise ValueError("Name cannot be blank")
        return v
class LoginIn(BaseModel): email: EmailStr; password: str = Field(min_length=1,max_length=128)
class ProfilePatch(BaseModel):
    full_name: str|None = Field(default=None,min_length=2,max_length=60)
    focus_goal: str|None = Field(default=None,max_length=120)
class TaskCreate(BaseModel):
    title: str = Field(min_length=1,max_length=120)
    description: str = Field(default="",max_length=2000)
    status: Status = "Planned"
    priority: Priority = "Medium"
    complexity: int = Field(default=3,ge=1,le=5)
    deadline: datetime|None = None
    planned_start: datetime|None = None
    estimated_duration_hours: float = Field(default=2,gt=0,le=1000)
    @field_validator("title")
    @classmethod
    def trim_title(cls,v):
        v=v.strip()
        if not v: raise ValueError("Title cannot be blank")
        return v
class ManagerTaskCreate(BaseModel):
    employee_email: EmailStr
    title: str = Field(min_length=1,max_length=120)
    description: str = Field(default="",max_length=2000)
    priority: Priority = "Medium"
    complexity: int = Field(default=3,ge=1,le=5)
    deadline: datetime|None = None
    planned_start: datetime|None = None
    estimated_duration_hours: float = Field(default=2,gt=0,le=1000)
class TaskPatch(BaseModel):
    title: str|None = Field(default=None,min_length=1,max_length=120)
    description: str|None = Field(default=None,max_length=2000)
    status: Status|None = None
    priority: Priority|None = None
    complexity: int|None = Field(default=None,ge=1,le=5)
    deadline: datetime|None = None
    planned_start: datetime|None = None
    estimated_duration_hours: float|None = Field(default=None,gt=0,le=1000)
class StatusPatch(BaseModel): status: Status
class PredictionIn(BaseModel):
    complexity: int = Field(ge=1,le=5)
    priority: Priority = "Medium"
    estimated_duration_hours: float = Field(gt=0,le=1000)
    active_tasks: int = Field(default=0,ge=0,le=10000)
    historical_avg_hours: float|None = Field(default=None,gt=0,le=10000)
    on_time_rate: float|None = Field(default=None,ge=0,le=1)
    hours_until_deadline: float|None = Field(default=None,ge=0,le=100000)
class NotificationRead(BaseModel): read: bool = True
