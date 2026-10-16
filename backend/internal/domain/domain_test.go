package domain

import (
	"errors"
	"testing"
	"time"
)

func ptr[T any](v T) *T { return &v }

func completeApplicant() Applicant {
	return Applicant{
		Borrower:              ptr("Петров Иван Иванович"),
		Dependents:            ptr(1),
		Housing:               ptr(HousingOwn),
		Age:                   ptr(32),
		Phone:                 ptr(true),
		ResidenceYears:        ptr(5),
		MaritalStatus:         ptr(MaritalMarried),
		ForeignWorker:         ptr(false),
		Property:              ptr(PropertyCar),
		Job:                   ptr(JobSkilled),
		EmploymentMonths:      ptr(36),
		Amount:                ptr(int64(450000)),
		TermMonths:            ptr(36),
		Purpose:               ptr(PurposeUsedCar),
		InstallmentRate:       ptr(17.9),
		CheckingStatus:        ptr(Checking0To200),
		OtherInstallmentPlans: ptr(false),
		Savings:               ptr(Savings100To500),
		OtherDebtors:          ptr(false),
		CreditHistory:         ptr(CreditHistoryExistingPaid),
		ExistingCredits:       ptr(1),
	}
}

func TestValidate(t *testing.T) {
	a := completeApplicant()
	if err := a.Validate(true); err != nil {
		t.Fatalf("complete applicant: %v", err)
	}

	var empty Applicant
	if err := empty.Validate(false); err != nil {
		t.Fatalf("empty draft: %v", err)
	}
	var verr *ValidationError
	if err := empty.Validate(true); !errors.As(err, &verr) || len(verr.Fields) != 21 {
		t.Fatalf("empty non-draft: want 21 missing fields, got %v", err)
	}

	bad := completeApplicant()
	bad.Age = ptr(17)
	bad.Housing = ptr(Housing("castle"))
	if err := bad.Validate(false); !errors.As(err, &verr) ||
		verr.Fields["age"] != "must be between 18 and 100" || verr.Fields["housing"] == "" {
		t.Fatalf("draft with bad values: %v", err)
	}
}

func TestNormalizeBorrower(t *testing.T) {
	a := Applicant{Borrower: ptr("  Петров   Иван ")}
	a.Normalize()
	if *a.Borrower != "Петров Иван" {
		t.Fatalf("got %q", *a.Borrower)
	}
	a.Borrower = ptr("   ")
	a.Normalize()
	if a.Borrower != nil {
		t.Fatal("blank borrower must become nil")
	}
}

func TestScore(t *testing.T) {
	th := Thresholds{Approve: 0.25, Reject: 0.5}
	tests := []struct {
		name     string
		p        float64
		mutate   func(*Applicant)
		risk     Risk
		rec      Recommendation
		numRules int
	}{
		{"low", 0.1, nil, RiskLow, RecommendationApprove, 0},
		{"medium", 0.3, nil, RiskMedium, RecommendationReview, 0},
		{"high", 0.7, nil, RiskHigh, RecommendationReject, 0},
		{"short employment forces review", 0.1, func(a *Applicant) { a.EmploymentMonths = ptr(8) }, RiskLow, RecommendationReview, 1},
		{"rules never soften a reject", 0.7, func(a *Applicant) { a.CreditHistory = ptr(CreditHistoryDelayed) }, RiskHigh, RecommendationReject, 1},
		{"unemployed is one rule, not two", 0.1, func(a *Applicant) {
			a.Job = ptr(JobUnemployed)
			a.EmploymentMonths = ptr(0)
		}, RiskLow, RecommendationReview, 1},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			a := completeApplicant()
			if tt.mutate != nil {
				tt.mutate(&a)
			}
			s := Score(a, tt.p, th)
			if s.Risk != tt.risk || s.Recommendation != tt.rec || len(s.TriggeredRules) != tt.numRules {
				t.Fatalf("got %s/%s rules=%v", s.Risk, s.Recommendation, s.TriggeredRules)
			}
		})
	}
}

func TestDecide(t *testing.T) {
	d, err := NewDecision(DecisionApprove, "  ok  ", 1, time.Now())
	if err != nil || d.Reason != "ok" {
		t.Fatalf("NewDecision: %v %q", err, d.Reason)
	}
	if _, err := NewDecision("maybe", " ", 1, time.Now()); err == nil {
		t.Fatal("want validation error")
	}

	draft := Application{Status: StatusDraft}
	if err := draft.Decide(d); !errors.Is(err, ErrDraftDecision) {
		t.Fatalf("draft: %v", err)
	}
	app := Application{Status: StatusManualReview}
	if err := app.Decide(d); err != nil || app.Status != StatusCompleted || app.Decision == nil {
		t.Fatalf("decide: %v %s", err, app.Status)
	}
}

func TestEdit(t *testing.T) {
	draft := Application{Status: StatusDraft}
	if err := draft.Edit(Applicant{Borrower: ptr("  Анна  ")}, true); err != nil || *draft.Applicant.Borrower != "Анна" {
		t.Fatalf("edit draft: %v", err)
	}
	var verr *ValidationError
	if err := draft.Edit(Applicant{}, false); !errors.As(err, &verr) {
		t.Fatalf("submit incomplete draft: %v", err)
	}
	if err := draft.Edit(completeApplicant(), false); err != nil {
		t.Fatalf("submit draft: %v", err)
	}

	scored := Application{Status: StatusManualReview, Scoring: &Scoring{}}
	if err := scored.Edit(completeApplicant(), true); !errors.Is(err, ErrRevertToDraft) {
		t.Fatalf("revert to draft: %v", err)
	}
	if err := scored.Edit(completeApplicant(), false); err != nil || scored.Scoring != nil {
		t.Fatalf("edit scored: %v", err)
	}
	scored.ApplyScoring(Scoring{Recommendation: RecommendationReject})
	if scored.Status != StatusNew {
		t.Fatalf("status after rescoring: %s", scored.Status)
	}

	done := Application{Status: StatusCompleted}
	if err := done.Edit(completeApplicant(), false); !errors.Is(err, ErrCompletedEdit) {
		t.Fatalf("edit completed: %v", err)
	}
}

func TestEnsureDeletable(t *testing.T) {
	if err := (&Application{Status: StatusDraft}).EnsureDeletable(); err != nil {
		t.Fatal(err)
	}
	if err := (&Application{Status: StatusNew}).EnsureDeletable(); !errors.Is(err, ErrNotDraft) {
		t.Fatalf("got %v", err)
	}
}
