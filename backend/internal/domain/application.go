package domain

import (
	"fmt"
	"strings"
	"time"
)

type Applicant struct {
	Borrower              *string
	Dependents            *int
	Housing               *Housing
	Age                   *int
	Phone                 *bool
	ResidenceYears        *int
	MaritalStatus         *MaritalStatus
	ForeignWorker         *bool
	Property              *Property
	Job                   *Job
	EmploymentMonths      *int
	Amount                *int64
	TermMonths            *int
	Purpose               *Purpose
	InstallmentRate       *float64
	CheckingStatus        *CheckingStatus
	OtherInstallmentPlans *bool
	Savings               *Savings
	OtherDebtors          *bool
	CreditHistory         *CreditHistory
	ExistingCredits       *int
}

type Thresholds struct {
	Approve float64
	Reject  float64
}

type Scoring struct {
	DefaultProbability float64
	Thresholds         Thresholds
	Risk               Risk
	Recommendation     Recommendation
	TriggeredRules     []string
}

type SpecialistDecision struct {
	Decision  Decision
	Reason    string
	DecidedBy int64
	DecidedAt time.Time
}

type Application struct {
	ID        int64
	ClientID  string
	Status    Status
	CreatedBy int64
	CreatedAt time.Time
	Applicant Applicant
	Scoring   *Scoring
	Decision  *SpecialistDecision
}

func (a *Applicant) Normalize() {
	if a.Borrower != nil {
		name := strings.Join(strings.Fields(*a.Borrower), " ")
		if name == "" {
			a.Borrower = nil
		} else {
			a.Borrower = &name
		}
	}
}

func (a *Applicant) Validate(complete bool) error {
	v := validator{}

	required := func(field string, isNil bool) {
		if complete && isNil {
			v.add(field, "is required")
		}
	}
	intRange := func(field string, p *int, lo, hi int) {
		required(field, p == nil)
		if p != nil && (*p < lo || *p > hi) {
			v.add(field, rangeMsg(lo, hi))
		}
	}
	enum := func(field string, isNil, valid bool) {
		required(field, isNil)
		if !isNil && !valid {
			v.add(field, "has an unknown value")
		}
	}
	const noLimit = int(^uint(0) >> 1)

	required("borrower", a.Borrower == nil)
	if a.Borrower != nil && len([]rune(*a.Borrower)) > 255 {
		v.add("borrower", "must be at most 255 characters")
	}
	intRange("dependents", a.Dependents, 0, 50)
	enum("housing", a.Housing == nil, a.Housing != nil && a.Housing.Valid())
	intRange("age", a.Age, 18, 100)
	required("phone", a.Phone == nil)
	intRange("residence_years", a.ResidenceYears, 0, 100)
	enum("marital_status", a.MaritalStatus == nil, a.MaritalStatus != nil && a.MaritalStatus.Valid())
	required("foreign_worker", a.ForeignWorker == nil)
	enum("property", a.Property == nil, a.Property != nil && a.Property.Valid())
	enum("job", a.Job == nil, a.Job != nil && a.Job.Valid())
	intRange("employment_months", a.EmploymentMonths, 0, 1200)
	required("amount", a.Amount == nil)
	if a.Amount != nil && *a.Amount < 1 {
		v.add("amount", "must be at least 1")
	}
	intRange("term_months", a.TermMonths, 1, 600)
	enum("purpose", a.Purpose == nil, a.Purpose != nil && a.Purpose.Valid())
	required("installment_rate", a.InstallmentRate == nil)
	if a.InstallmentRate != nil && (*a.InstallmentRate < 0 || *a.InstallmentRate > 100) {
		v.add("installment_rate", "must be between 0 and 100")
	}
	enum("checking_status", a.CheckingStatus == nil, a.CheckingStatus != nil && a.CheckingStatus.Valid())
	required("other_installment_plans", a.OtherInstallmentPlans == nil)
	enum("savings", a.Savings == nil, a.Savings != nil && a.Savings.Valid())
	required("other_debtors", a.OtherDebtors == nil)
	enum("credit_history", a.CreditHistory == nil, a.CreditHistory != nil && a.CreditHistory.Valid())
	intRange("existing_credits", a.ExistingCredits, 0, noLimit)

	return v.err()
}

func rangeMsg(lo, hi int) string {
	if hi == int(^uint(0)>>1) {
		return fmt.Sprintf("must be at least %d", lo)
	}
	return fmt.Sprintf("must be between %d and %d", lo, hi)
}

func NewDecision(decision Decision, reason string, by int64, at time.Time) (SpecialistDecision, error) {
	v := validator{}
	if !decision.Valid() {
		v.add("decision", "must be approve or reject")
	}
	reason = strings.TrimSpace(reason)
	if reason == "" {
		v.add("reason", "is required")
	}
	if err := v.err(); err != nil {
		return SpecialistDecision{}, err
	}
	return SpecialistDecision{Decision: decision, Reason: reason, DecidedBy: by, DecidedAt: at}, nil
}

func (app *Application) Decide(d SpecialistDecision) error {
	if app.Status == StatusDraft {
		return ErrDraftDecision
	}
	app.Decision = &d
	app.Status = StatusCompleted
	return nil
}

func (app *Application) Edit(a Applicant, draft bool) error {
	if app.Status == StatusCompleted {
		return ErrCompletedEdit
	}
	if draft && app.Status != StatusDraft {
		return ErrRevertToDraft
	}
	a.Normalize()
	if err := a.Validate(!draft); err != nil {
		return err
	}
	app.Applicant = a
	app.Scoring = nil
	app.Status = StatusDraft
	return nil
}

func (app *Application) ApplyScoring(s Scoring) {
	app.Scoring = &s
	app.Status = StatusFor(s.Recommendation)
}

func (app *Application) EnsureDeletable() error {
	if app.Status != StatusDraft {
		return ErrNotDraft
	}
	return nil
}
