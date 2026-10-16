package domain

type (
	Risk           string
	Recommendation string
	Status         string
	Decision       string
	MaritalStatus  string
	Housing        string
	Property       string
	Job            string
	Purpose        string
	CreditHistory  string
	CheckingStatus string
	Savings        string
)

const (
	RiskLow    Risk = "low"
	RiskMedium Risk = "medium"
	RiskHigh   Risk = "high"
)

const (
	RecommendationApprove Recommendation = "approve"
	RecommendationReview  Recommendation = "review"
	RecommendationReject  Recommendation = "reject"
)

const (
	StatusDraft               Status = "draft"
	StatusNew                 Status = "new"
	StatusManualReview        Status = "manual_review"
	StatusPendingConfirmation Status = "pending_confirmation"
	StatusCompleted           Status = "completed"
)

const (
	DecisionApprove Decision = "approve"
	DecisionReject  Decision = "reject"
)

const (
	MaritalSingle   MaritalStatus = "single"
	MaritalMarried  MaritalStatus = "married"
	MaritalDivorced MaritalStatus = "divorced"
	MaritalWidowed  MaritalStatus = "widowed"
)

const (
	HousingOwn  Housing = "own"
	HousingRent Housing = "rent"
	HousingFree Housing = "free"
)

const (
	PropertyRealEstate       Property = "real_estate"
	PropertySavingsInsurance Property = "savings_insurance"
	PropertyCar              Property = "car"
	PropertyNone             Property = "none"
)

const (
	JobUnemployed Job = "unemployed"
	JobUnskilled  Job = "unskilled"
	JobSkilled    Job = "skilled"
	JobManagement Job = "management"
)

const (
	PurposeNewCar      Purpose = "new_car"
	PurposeUsedCar     Purpose = "used_car"
	PurposeFurniture   Purpose = "furniture"
	PurposeElectronics Purpose = "electronics"
	PurposeRepairs     Purpose = "repairs"
	PurposeEducation   Purpose = "education"
	PurposeRetraining  Purpose = "retraining"
	PurposeBusiness    Purpose = "business"
	PurposeOther       Purpose = "other"
)

const (
	CreditHistoryNoCredits    CreditHistory = "no_credits"
	CreditHistoryAllPaid      CreditHistory = "all_paid"
	CreditHistoryExistingPaid CreditHistory = "existing_paid"
	CreditHistoryDelayed      CreditHistory = "delayed"
	CreditHistoryCritical     CreditHistory = "critical"
)

const (
	CheckingNone   CheckingStatus = "none"
	CheckingLt0    CheckingStatus = "lt_0"
	Checking0To200 CheckingStatus = "0_200"
	CheckingGe200  CheckingStatus = "ge_200"
)

const (
	SavingsUnknown   Savings = "unknown"
	SavingsLt100     Savings = "lt_100"
	Savings100To500  Savings = "100_500"
	Savings500To1000 Savings = "500_1000"
	SavingsGe1000    Savings = "ge_1000"
)

func oneOf[T ~string](v T, allowed ...T) bool {
	for _, a := range allowed {
		if v == a {
			return true
		}
	}
	return false
}

func (r Risk) Valid() bool { return oneOf(r, RiskLow, RiskMedium, RiskHigh) }

func (r Recommendation) Valid() bool {
	return oneOf(r, RecommendationApprove, RecommendationReview, RecommendationReject)
}

func (s Status) Valid() bool {
	return oneOf(s, StatusDraft, StatusNew, StatusManualReview, StatusPendingConfirmation, StatusCompleted)
}

func (d Decision) Valid() bool { return oneOf(d, DecisionApprove, DecisionReject) }

func (m MaritalStatus) Valid() bool {
	return oneOf(m, MaritalSingle, MaritalMarried, MaritalDivorced, MaritalWidowed)
}

func (h Housing) Valid() bool { return oneOf(h, HousingOwn, HousingRent, HousingFree) }

func (p Property) Valid() bool {
	return oneOf(p, PropertyRealEstate, PropertySavingsInsurance, PropertyCar, PropertyNone)
}

func (j Job) Valid() bool { return oneOf(j, JobUnemployed, JobUnskilled, JobSkilled, JobManagement) }

func (p Purpose) Valid() bool {
	return oneOf(p, PurposeNewCar, PurposeUsedCar, PurposeFurniture, PurposeElectronics, PurposeRepairs,
		PurposeEducation, PurposeRetraining, PurposeBusiness, PurposeOther)
}

func (c CreditHistory) Valid() bool {
	return oneOf(c, CreditHistoryNoCredits, CreditHistoryAllPaid, CreditHistoryExistingPaid,
		CreditHistoryDelayed, CreditHistoryCritical)
}

func (c CheckingStatus) Valid() bool {
	return oneOf(c, CheckingNone, CheckingLt0, Checking0To200, CheckingGe200)
}

func (s Savings) Valid() bool {
	return oneOf(s, SavingsUnknown, SavingsLt100, Savings100To500, Savings500To1000, SavingsGe1000)
}
