from datetime import date
from typing import Literal
import re
from pydantic import BaseModel, Field, ConfigDict, field_validator

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
class FieldValidationError(BaseModel):
    field:str
    message:str
    type:str
class ValidationResponse(BaseModel):
    detail:str
    errors:list[FieldValidationError]
class Credentials(Strict):
    email: str = Field(min_length=3, max_length=250)
    password: str = Field(min_length=10, max_length=200)

    @field_validator('email',mode='before')
    @classmethod
    def normalize_email(cls,value):
        return value.strip().lower() if isinstance(value,str) else value

    @field_validator('email')
    @classmethod
    def valid_email(cls,value):
        if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',value):raise ValueError('Enter a valid email address.')
        return value

    @field_validator('password')
    @classmethod
    def not_blank_password(cls,value):
        if not value.strip():raise ValueError('Choose a password with at least 10 characters, including a non-space character.')
        return value
class ComplaintInput(Strict):
    village_id: str
    description: str = Field(min_length=10, max_length=10000)
    category: Literal['shortage', 'interruption', 'irrigation', 'leakage', 'other']
    consent: Literal[True]
class Review(Strict):
    status: Literal['accepted', 'rejected', 'needs_information', 'duplicate', 'withdrawn', 'submitted']
    reason: str = Field(min_length=5, max_length=4000)
    expected_version: int
    jurisdiction: str | None = None
    duplicate_of: str | None = None
    sanitized_description: str | None = Field(default=None, min_length=10, max_length=10000)
class Action(Strict):
    status: Literal['acknowledged', 'assigned', 'in_progress', 'needs_clarification', 'resolved', 'reopened']
    note: str = Field(min_length=5, max_length=4000)
    expected_version: int
class Message(Strict):
    text: str = Field(min_length=1, max_length=4000)
    village_id: str | None = None
class FarmInput(Strict):
    village_id: str
    crop: str = Field(min_length=2, max_length=100)
    area_ha: float = Field(gt=0, le=10000)
    sowing_date: date
    irrigation_method: Literal['drip', 'sprinkler', 'surface']
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
class BaselineInput(Strict):
    sector: Literal['household', 'agriculture', 'livestock', 'other']
    litres_per_day: float = Field(ge=0)
    method: str = Field(min_length=5)
    source: str = Field(min_length=5)
    reference_start: date
    reference_end: date
    valid_from: date
    valid_to: date
    uses_covered: str = Field(min_length=3)
    assumptions: str = Field(min_length=5)
    uncertainty: str = Field(min_length=3)
class PlanInput(Strict):
    area_ha: float = Field(gt=0)
    et0: float = Field(ge=0, le=30)
    kc: float = Field(ge=0, le=2)
    effective_rain: float = Field(ge=0)
    efficiency: float = Field(gt=0, le=1)
    soil_contribution: float = Field(default=0, ge=0)
    cap_litres: float | None = Field(default=None, ge=0)
class AssistantInput(Strict):
    village_id: str
    question: str = Field(min_length=2, max_length=2000)
    language: Literal['mr', 'en'] = 'mr'
    days: Literal[7, 15] = 7
    consent: bool = False
class UploadInput(Strict):
    complaint_id: str
    content_type: Literal['image/jpeg', 'image/png']
    size: int = Field(gt=0, le=5242880)
    sha256: str = Field(pattern='^[a-f0-9]{64}$')
class EconomicsInput(Strict):
    yield_kg: float = Field(ge=0)
    price_per_kg: float = Field(ge=0)
    cultivation_cost: float = Field(ge=0)
    transport_cost: float = Field(ge=0)
    assumptions: str = Field(min_length=5)
