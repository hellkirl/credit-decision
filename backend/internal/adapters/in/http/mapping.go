package http

import (
	"github.com/hellkirl/credit-decision/internal/domain"
	genhttp "github.com/hellkirl/credit-decision/pkg/generated/http"
)

func fromInput(in genhttp.ApplicationInput) domain.Applicant {
	return domain.Applicant{
		Borrower:              in.Borrower,
		Dependents:            in.Dependents,
		Housing:               (*domain.Housing)(in.Housing),
		Age:                   in.Age,
		Phone:                 in.Phone,
		ResidenceYears:        in.ResidenceYears,
		MaritalStatus:         (*domain.MaritalStatus)(in.MaritalStatus),
		ForeignWorker:         in.ForeignWorker,
		Property:              (*domain.Property)(in.Property),
		Job:                   (*domain.Job)(in.Job),
		EmploymentMonths:      in.EmploymentMonths,
		Amount:                in.Amount,
		TermMonths:            in.TermMonths,
		Purpose:               (*domain.Purpose)(in.Purpose),
		InstallmentRate:       in.InstallmentRate,
		CheckingStatus:        (*domain.CheckingStatus)(in.CheckingStatus),
		OtherInstallmentPlans: in.OtherInstallmentPlans,
		Savings:               (*domain.Savings)(in.Savings),
		OtherDebtors:          in.OtherDebtors,
		CreditHistory:         (*domain.CreditHistory)(in.CreditHistory),
		ExistingCredits:       in.ExistingCredits,
	}
}

func toSummary(app domain.Application) genhttp.ApplicationSummary {
	s := genhttp.ApplicationSummary{
		Id:        app.ID,
		Borrower:  app.Applicant.Borrower,
		Amount:    app.Applicant.Amount,
		Status:    genhttp.Status(app.Status),
		CreatedAt: app.CreatedAt,
	}
	if sc := app.Scoring; sc != nil {
		s.Risk = (*genhttp.Risk)(&sc.Risk)
		s.Recommendation = (*genhttp.Recommendation)(&sc.Recommendation)
	}
	return s
}

func toDetail(app domain.Application) genhttp.ApplicationDetail {
	a := app.Applicant
	d := genhttp.ApplicationDetail{
		Id:        app.ID,
		ClientId:  app.ClientID,
		Status:    genhttp.Status(app.Status),
		CreatedAt: app.CreatedAt,

		Borrower:              a.Borrower,
		Dependents:            a.Dependents,
		Housing:               (*genhttp.Housing)(a.Housing),
		Age:                   a.Age,
		Phone:                 a.Phone,
		ResidenceYears:        a.ResidenceYears,
		MaritalStatus:         (*genhttp.MaritalStatus)(a.MaritalStatus),
		ForeignWorker:         a.ForeignWorker,
		Property:              (*genhttp.Property)(a.Property),
		Job:                   (*genhttp.Job)(a.Job),
		EmploymentMonths:      a.EmploymentMonths,
		Amount:                a.Amount,
		TermMonths:            a.TermMonths,
		Purpose:               (*genhttp.Purpose)(a.Purpose),
		InstallmentRate:       a.InstallmentRate,
		CheckingStatus:        (*genhttp.CheckingStatus)(a.CheckingStatus),
		OtherInstallmentPlans: a.OtherInstallmentPlans,
		Savings:               (*genhttp.Savings)(a.Savings),
		OtherDebtors:          a.OtherDebtors,
		CreditHistory:         (*genhttp.CreditHistory)(a.CreditHistory),
		ExistingCredits:       a.ExistingCredits,

		TriggeredRules: []string{},
	}
	if sc := app.Scoring; sc != nil {
		d.Risk = (*genhttp.Risk)(&sc.Risk)
		d.Recommendation = (*genhttp.Recommendation)(&sc.Recommendation)
		d.DefaultProbability = sc.DefaultProbability
		d.Thresholds = &genhttp.Thresholds{Approve: sc.Thresholds.Approve, Reject: sc.Thresholds.Reject}
		if sc.TriggeredRules != nil {
			d.TriggeredRules = sc.TriggeredRules
		}
	}
	if dec := app.Decision; dec != nil {
		d.Decision = &genhttp.DecisionInput{Decision: genhttp.Decision(dec.Decision), Reason: dec.Reason}
	}
	return d
}
