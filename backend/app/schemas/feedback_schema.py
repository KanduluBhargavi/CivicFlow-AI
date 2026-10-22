from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):

    complaint_id: int | None = None

    rating: int = Field(
        ge=1,
        le=5
    )

    message: str = Field(
        min_length=3,
        max_length=2000
    )