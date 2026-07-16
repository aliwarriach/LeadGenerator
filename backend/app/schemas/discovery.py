import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Hard cap on comma-separated cities per request — a discovery request fans
# out into (sources x cities) ARQ jobs, so this bounds the blast radius of a
# single call rather than letting one request silently queue dozens of jobs.
MAX_CITIES_PER_REQUEST = 10


class DiscoveryRequest(BaseModel):
    country: str = Field(min_length=1, max_length=100, description="e.g. 'Pakistan'")
    city: str = Field(
        min_length=1,
        max_length=512,
        description="e.g. 'Lahore' or 'Lahore, Karachi' (comma-separated for multiple cities)",
    )
    custom_niche: str = Field(
        min_length=1, max_length=256, description="e.g. 'Dental Clinics', 'Med Spas', 'orthodontists'"
    )
    min_rating: float | None = Field(
        default=None, ge=0, le=5, description="Minimum Google Maps rating, e.g. 4.0"
    )

    @field_validator("city")
    @classmethod
    def _validate_and_normalize_cities(cls, value: str) -> str:
        cities = [city.strip() for city in value.split(",") if city.strip()]
        if not cities:
            raise ValueError("city must contain at least one non-empty value")
        if len(cities) > MAX_CITIES_PER_REQUEST:
            raise ValueError(f"at most {MAX_CITIES_PER_REQUEST} cities allowed per request")
        return ", ".join(cities)

    @property
    def cities(self) -> list[str]:
        return [city.strip() for city in self.city.split(",") if city.strip()]


class DiscoveryJobRef(BaseModel):
    source: Literal["google_maps", "facebook", "serper"]
    city: str
    job_id: uuid.UUID


class DiscoveryResponse(BaseModel):
    run_id: uuid.UUID
    country: str
    city: str
    custom_niche: str
    min_rating: float | None
    jobs: list[DiscoveryJobRef]
