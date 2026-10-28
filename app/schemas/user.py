from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class UserRead(BaseModel):
    id: int
    email: EmailStr
    username: str
    full_name: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProfileUpdate(BaseModel):
    username: str | None = Field(
        default=None, min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_.]+$"
    )
    full_name: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def require_an_update(self) -> "ProfileUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one profile field to update")
        if "username" in self.model_fields_set and self.username is None:
            raise ValueError("Username cannot be null")
        return self
