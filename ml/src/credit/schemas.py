from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CreditApplication(BaseModel):
    status: int = Field(
        ...,
        ge=1,
        le=4,
        description="Checking account status (1=none … 4=≥200 DM / salary)",
        examples=[1],
    )
    duration: int = Field(
        ...,
        gt=0,
        description="Credit duration in months",
        examples=[18],
    )
    credit_history: int = Field(
        ...,
        ge=0,
        le=4,
        description="Credit history code (0=delay … 4=all paid at this bank)",
        examples=[4],
    )
    purpose: int = Field(
        ...,
        ge=0,
        le=10,
        description="Loan purpose (0=others … 10=business)",
        examples=[2],
    )
    amount: int = Field(
        ...,
        gt=0,
        description="Credit amount in DM",
        examples=[1049],
    )
    savings: int = Field(
        ...,
        ge=1,
        le=5,
        description="Savings account (1=unknown/none … 5=≥1000 DM)",
        examples=[1],
    )
    employment_duration: int = Field(
        ...,
        ge=1,
        le=5,
        description="Employment duration (1=unemployed … 5=≥7 yrs)",
        examples=[2],
    )
    installment_rate: int = Field(
        ...,
        ge=1,
        le=4,
        description="Installment rate as % of disposable income (1=≥35 … 4=<20)",
        examples=[4],
    )
    personal_status_sex: int = Field(
        ...,
        ge=1,
        le=4,
        description="Personal status / sex",
        examples=[2],
    )
    other_debtors: int = Field(
        ...,
        ge=1,
        le=3,
        description="Other debtors / guarantors (1=none, 2=co-applicant, 3=guarantor)",
        examples=[1],
    )
    present_residence: int = Field(
        ...,
        ge=1,
        le=4,
        description="Years at present residence (1=<1 … 4=≥7)",
        examples=[4],
    )
    property: int = Field(
        ...,
        ge=1,
        le=4,
        description="Most valuable property (1=none … 4=real estate)",
        examples=[2],
    )
    age: int = Field(
        ...,
        ge=18,
        le=100,
        description="Age in years",
        examples=[21],
    )
    other_installment_plans: int = Field(
        ...,
        ge=1,
        le=3,
        description="Other installment plans (1=bank, 2=stores, 3=none)",
        examples=[3],
    )
    housing: int = Field(
        ...,
        ge=1,
        le=3,
        description="Housing (1=for free, 2=rent, 3=own)",
        examples=[1],
    )
    number_credits: int = Field(
        ...,
        ge=1,
        le=4,
        description="Number of existing credits (1=1 … 4=≥6)",
        examples=[1],
    )
    job: int = Field(
        ...,
        ge=1,
        le=4,
        description="Job / skill level (1=unskilled non-resident … 4=manager)",
        examples=[3],
    )
    people_liable: int = Field(
        ...,
        ge=1,
        le=2,
        description="People liable to provide maintenance (1=3 or more, 2=0 to 2)",
        examples=[2],
    )
    telephone: int = Field(
        ...,
        ge=1,
        le=2,
        description="Telephone (1=no, 2=yes under customer name)",
        examples=[1],
    )
    foreign_worker: int = Field(
        ...,
        ge=1,
        le=2,
        description="Foreign worker (1=yes, 2=no)",
        examples=[2],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": 1,
                    "duration": 18,
                    "credit_history": 4,
                    "purpose": 2,
                    "amount": 1049,
                    "savings": 1,
                    "employment_duration": 2,
                    "installment_rate": 4,
                    "personal_status_sex": 2,
                    "other_debtors": 1,
                    "present_residence": 4,
                    "property": 2,
                    "age": 21,
                    "other_installment_plans": 3,
                    "housing": 1,
                    "number_credits": 1,
                    "job": 3,
                    "people_liable": 2,
                    "telephone": 1,
                    "foreign_worker": 2,
                }
            ]
        }
    }


class PredictionResponse(BaseModel):
    credit_risk: Literal["bad", "good"] = Field(
        ...,
        description="Predicted class: bad=0, good=1",
    )
    credit_risk_code: int = Field(..., ge=0, le=1, description="0=bad, 1=good")
    probability_good: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Estimated P(credit_risk = good)",
    )
    probability_bad: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Estimated P(credit_risk = bad)",
    )
    threshold: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Decision threshold applied to probability_good",
    )


class BatchPredictionRequest(BaseModel):
    applications: list[CreditApplication] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Up to 100 applications per request",
    )


class BatchPredictionResponse(BaseModel):
    predictions: list[PredictionResponse]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    model_loaded: bool
    threshold: float


class MetricsResponse(BaseModel):
    threshold: float
    accuracy: float | None = None
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None
    roc_auc: float | None = None
