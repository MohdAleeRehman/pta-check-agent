from pydantic import BaseModel, Field, validator
import re
from typing import Optional, Literal
from datetime import datetime


class IMEIRequest(BaseModel):
    """Request model for IMEI verification."""

    imei: str = Field(..., description="IMEI number to verify")

    @validator("imei")
    def validate_imei(cls, v):
        """Validate IMEI format."""
        # IMEI should be 15 digits
        if not re.match(r"^\d{15}$", v):
            raise ValueError("IMEI must be exactly 15 digits")
        return v


class CaptchaSolution(BaseModel):
    """Model for captcha solution."""

    solution: str
    captcha_id: Optional[str] = None
    error: Optional[str] = None
    success: bool = True


class PTAVerificationResult(BaseModel):
    """Model for PTA verification result."""

    imei: str
    status: Optional[Literal["Compliant", "Non-Compliant", "Error"]] = None
    details: Optional[dict] = None
    error_message: Optional[str] = None
    verification_date: datetime = Field(default_factory=datetime.now)


class SupabaseRecord(BaseModel):
    """Model for Supabase record."""

    imei: str
    status: Literal["Compliant", "Non-Compliant", "Error"]
    details: Optional[dict] = None
    error_message: Optional[str] = None
    verification_date: datetime = Field(default_factory=datetime.now)

    def dict(self, *args, **kwargs):
        """Override dict method to handle datetime serialization."""
        data = super().dict(*args, **kwargs)
        # Convert datetime to ISO format string for JSON serialization
        if isinstance(data.get("verification_date"), datetime):
            data["verification_date"] = data["verification_date"].isoformat()
        return data
