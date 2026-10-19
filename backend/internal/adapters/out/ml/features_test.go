package ml

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/hellkirl/credit-decision/internal/domain"
	genml "github.com/hellkirl/credit-decision/pkg/generated/ml"
)

func ptr[T any](v T) *T { return &v }

func applicant() domain.Applicant {
	return domain.Applicant{
		Borrower:              ptr("Петров Иван Иванович"),
		Dependents:            ptr(3),
		Housing:               ptr(domain.HousingRent),
		Age:                   ptr(32),
		Phone:                 ptr(true),
		ResidenceYears:        ptr(5),
		MaritalStatus:         ptr(domain.MaritalSingle),
		ForeignWorker:         ptr(false),
		Property:              ptr(domain.PropertyRealEstate),
		Job:                   ptr(domain.JobSkilled),
		EmploymentMonths:      ptr(8),
		Amount:                ptr(int64(450000)),
		TermMonths:            ptr(36),
		Purpose:               ptr(domain.PurposeBusiness),
		InstallmentRate:       ptr(17.9),
		CheckingStatus:        ptr(domain.CheckingLt0),
		OtherInstallmentPlans: ptr(true),
		Savings:               ptr(domain.SavingsGe1000),
		OtherDebtors:          ptr(false),
		CreditHistory:         ptr(domain.CreditHistoryDelayed),
		ExistingCredits:       ptr(2),
	}
}

func TestToFeatures(t *testing.T) {
	got, err := toFeatures(applicant(), 100)
	if err != nil {
		t.Fatal(err)
	}
	want := genml.CreditApplication{
		Status: 2, Duration: 36, CreditHistory: 0, Purpose: 10, Amount: 4500, Savings: 5,
		EmploymentDuration: 2, InstallmentRate: 4, PersonalStatusSex: 2, OtherDebtors: 1,
		PresentResidence: 3, Property: 4, Age: 32, OtherInstallmentPlans: 1, Housing: 2,
		NumberCredits: 2, Job: 3, PeopleLiable: 1, Telephone: 2, ForeignWorker: 2,
	}
	if got != want {
		t.Fatalf("got  %+v\nwant %+v", got, want)
	}

	incomplete := applicant()
	incomplete.Age = nil
	if _, err := toFeatures(incomplete, 100); err == nil {
		t.Fatal("want error for incomplete applicant")
	}
}

func TestPredict(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/predict" {
			http.NotFound(w, r)
			return
		}
		var f genml.CreditApplication
		if err := json.NewDecoder(r.Body).Decode(&f); err != nil || f.Amount != 4500 {
			http.Error(w, "bad body", http.StatusUnprocessableEntity)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"credit_risk":"good","credit_risk_code":1,"probability_good":0.8,"probability_bad":0.2,"decision":"approve","reasons":[],"threshold":0.6}`))
	}))
	defer srv.Close()

	c, err := NewClient(srv.URL, time.Second, 100)
	if err != nil {
		t.Fatal(err)
	}
	p, err := c.Predict(context.Background(), applicant())
	if err != nil {
		t.Fatal(err)
	}
	if p.DefaultProbability == nil || *p.DefaultProbability != 0.2 ||
		p.Recommendation != domain.RecommendationApprove || len(p.TriggeredRules) != 0 {
		t.Fatalf("got %+v", p)
	}
}
