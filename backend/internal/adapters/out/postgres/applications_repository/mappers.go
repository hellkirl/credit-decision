package applicationsrepository

import (
	"github.com/hellkirl/credit-decision/internal/domain"
)

func toDTO(app *domain.Application) ApplicationDTO {
	a := app.Applicant
	d := ApplicationDTO{
		ID:        app.ID,
		ClientID:  app.ClientID,
		Status:    string(app.Status),
		CreatedBy: app.CreatedBy,
		CreatedAt: app.CreatedAt,

		Borrower:              a.Borrower,
		Dependents:            a.Dependents,
		Housing:               (*string)(a.Housing),
		Age:                   a.Age,
		Phone:                 a.Phone,
		ResidenceYears:        a.ResidenceYears,
		MaritalStatus:         (*string)(a.MaritalStatus),
		ForeignWorker:         a.ForeignWorker,
		Property:              (*string)(a.Property),
		Job:                   (*string)(a.Job),
		EmploymentMonths:      a.EmploymentMonths,
		Amount:                a.Amount,
		TermMonths:            a.TermMonths,
		Purpose:               (*string)(a.Purpose),
		InstallmentRate:       a.InstallmentRate,
		CheckingStatus:        (*string)(a.CheckingStatus),
		OtherInstallmentPlans: a.OtherInstallmentPlans,
		Savings:               (*string)(a.Savings),
		OtherDebtors:          a.OtherDebtors,
		CreditHistory:         (*string)(a.CreditHistory),
		ExistingCredits:       a.ExistingCredits,

		TriggeredRules: []string{},
	}
	if s := app.Scoring; s != nil {
		d.DefaultProbability = s.DefaultProbability
		d.ApproveThreshold = &s.Thresholds.Approve
		d.RejectThreshold = &s.Thresholds.Reject
		d.Risk = (*string)(&s.Risk)
		d.Recommendation = (*string)(&s.Recommendation)
		if s.TriggeredRules != nil {
			d.TriggeredRules = s.TriggeredRules
		}
	}
	if dec := app.Decision; dec != nil {
		d.Decision = (*string)(&dec.Decision)
		d.DecisionReason = &dec.Reason
		d.DecidedBy = &dec.DecidedBy
		d.DecidedAt = &dec.DecidedAt
	}
	return d
}

func toDomain(d ApplicationDTO) *domain.Application {
	app := &domain.Application{
		ID:        d.ID,
		ClientID:  d.ClientID,
		Status:    domain.Status(d.Status),
		CreatedBy: d.CreatedBy,
		CreatedAt: d.CreatedAt.UTC(),
		Applicant: domain.Applicant{
			Borrower:              d.Borrower,
			Dependents:            d.Dependents,
			Housing:               (*domain.Housing)(d.Housing),
			Age:                   d.Age,
			Phone:                 d.Phone,
			ResidenceYears:        d.ResidenceYears,
			MaritalStatus:         (*domain.MaritalStatus)(d.MaritalStatus),
			ForeignWorker:         d.ForeignWorker,
			Property:              (*domain.Property)(d.Property),
			Job:                   (*domain.Job)(d.Job),
			EmploymentMonths:      d.EmploymentMonths,
			Amount:                d.Amount,
			TermMonths:            d.TermMonths,
			Purpose:               (*domain.Purpose)(d.Purpose),
			InstallmentRate:       d.InstallmentRate,
			CheckingStatus:        (*domain.CheckingStatus)(d.CheckingStatus),
			OtherInstallmentPlans: d.OtherInstallmentPlans,
			Savings:               (*domain.Savings)(d.Savings),
			OtherDebtors:          d.OtherDebtors,
			CreditHistory:         (*domain.CreditHistory)(d.CreditHistory),
			ExistingCredits:       d.ExistingCredits,
		},
	}
	if d.ApproveThreshold != nil && d.RejectThreshold != nil &&
		d.Risk != nil && d.Recommendation != nil {
		app.Scoring = &domain.Scoring{
			DefaultProbability: d.DefaultProbability,
			Thresholds:         domain.Thresholds{Approve: *d.ApproveThreshold, Reject: *d.RejectThreshold},
			Risk:               domain.Risk(*d.Risk),
			Recommendation:     domain.Recommendation(*d.Recommendation),
			TriggeredRules:     []string(d.TriggeredRules),
		}
	}
	if d.Decision != nil && d.DecisionReason != nil {
		dec := &domain.SpecialistDecision{Decision: domain.Decision(*d.Decision), Reason: *d.DecisionReason}
		if d.DecidedBy != nil {
			dec.DecidedBy = *d.DecidedBy
		}
		if d.DecidedAt != nil {
			dec.DecidedAt = d.DecidedAt.UTC()
		}
		app.Decision = dec
	}
	return app
}
