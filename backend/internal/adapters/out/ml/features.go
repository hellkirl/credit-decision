package ml

import (
	"errors"
	"math"

	"github.com/hellkirl/credit-decision/internal/domain"
	genml "github.com/hellkirl/credit-decision/pkg/generated/ml"
)

var (
	checkingCodes = map[domain.CheckingStatus]int{
		domain.CheckingNone: 1, domain.CheckingLt0: 2, domain.Checking0To200: 3, domain.CheckingGe200: 4,
	}
	creditHistoryCodes = map[domain.CreditHistory]int{
		domain.CreditHistoryDelayed:      0,
		domain.CreditHistoryCritical:     1,
		domain.CreditHistoryNoCredits:    2,
		domain.CreditHistoryExistingPaid: 3,
		domain.CreditHistoryAllPaid:      4,
	}
	purposeCodes = map[domain.Purpose]int{
		domain.PurposeOther:       0,
		domain.PurposeNewCar:      1,
		domain.PurposeUsedCar:     2,
		domain.PurposeFurniture:   3,
		domain.PurposeElectronics: 4,
		domain.PurposeRepairs:     6,
		domain.PurposeEducation:   7,
		domain.PurposeRetraining:  9,
		domain.PurposeBusiness:    10,
	}
	savingsCodes = map[domain.Savings]int{
		domain.SavingsUnknown: 1, domain.SavingsLt100: 2, domain.Savings100To500: 3,
		domain.Savings500To1000: 4, domain.SavingsGe1000: 5,
	}
	personalStatusCodes = map[domain.MaritalStatus]int{
		domain.MaritalDivorced: 1, domain.MaritalSingle: 2, domain.MaritalMarried: 3, domain.MaritalWidowed: 3,
	}
	propertyCodes = map[domain.Property]int{
		domain.PropertyNone: 1, domain.PropertyCar: 2, domain.PropertySavingsInsurance: 3, domain.PropertyRealEstate: 4,
	}
	housingCodes = map[domain.Housing]int{
		domain.HousingFree: 1, domain.HousingRent: 2, domain.HousingOwn: 3,
	}
	jobCodes = map[domain.Job]int{
		domain.JobUnemployed: 1, domain.JobUnskilled: 2, domain.JobSkilled: 3, domain.JobManagement: 4,
	}
)

var errIncomplete = errors.New("ml: applicant data is incomplete")

func toFeatures(a domain.Applicant, rubPerDM float64) (genml.CreditApplication, error) {
	if a.CheckingStatus == nil || a.TermMonths == nil || a.CreditHistory == nil || a.Purpose == nil ||
		a.Amount == nil || a.Savings == nil || a.Job == nil || a.EmploymentMonths == nil ||
		a.InstallmentRate == nil || a.MaritalStatus == nil || a.OtherDebtors == nil ||
		a.ResidenceYears == nil || a.Property == nil || a.Age == nil || a.OtherInstallmentPlans == nil ||
		a.Housing == nil || a.ExistingCredits == nil || a.Dependents == nil || a.Phone == nil ||
		a.ForeignWorker == nil {
		return genml.CreditApplication{}, errIncomplete
	}

	return genml.CreditApplication{
		Status:                checkingCodes[*a.CheckingStatus],
		Duration:              *a.TermMonths,
		CreditHistory:         creditHistoryCodes[*a.CreditHistory],
		Purpose:               purposeCodes[*a.Purpose],
		Amount:                max(1, int(math.Round(float64(*a.Amount)/rubPerDM))),
		Savings:               savingsCodes[*a.Savings],
		EmploymentDuration:    employmentCode(*a.Job, *a.EmploymentMonths),
		InstallmentRate:       installmentRateCode(*a.InstallmentRate),
		PersonalStatusSex:     personalStatusCodes[*a.MaritalStatus],
		OtherDebtors:          pick(*a.OtherDebtors, 2, 1),
		PresentResidence:      residenceCode(*a.ResidenceYears),
		Property:              propertyCodes[*a.Property],
		Age:                   *a.Age,
		OtherInstallmentPlans: pick(*a.OtherInstallmentPlans, 1, 3),
		Housing:               housingCodes[*a.Housing],
		NumberCredits:         creditsCode(*a.ExistingCredits),
		Job:                   jobCodes[*a.Job],
		PeopleLiable:          pick(*a.Dependents >= 3, 1, 2),
		Telephone:             pick(*a.Phone, 2, 1),
		ForeignWorker:         pick(*a.ForeignWorker, 1, 2),
	}, nil
}

func pick(cond bool, yes, no int) int {
	if cond {
		return yes
	}
	return no
}

func employmentCode(job domain.Job, months int) int {
	switch {
	case job == domain.JobUnemployed:
		return 1
	case months < 12:
		return 2
	case months < 48:
		return 3
	case months < 84:
		return 4
	default:
		return 5
	}
}

func installmentRateCode(pct float64) int {
	switch {
	case pct >= 35:
		return 1
	case pct >= 25:
		return 2
	case pct >= 20:
		return 3
	default:
		return 4
	}
}

func residenceCode(years int) int {
	switch {
	case years < 1:
		return 1
	case years < 4:
		return 2
	case years < 7:
		return 3
	default:
		return 4
	}
}

func creditsCode(n int) int {
	switch {
	case n <= 1:
		return 1
	case n <= 3:
		return 2
	case n <= 5:
		return 3
	default:
		return 4
	}
}
