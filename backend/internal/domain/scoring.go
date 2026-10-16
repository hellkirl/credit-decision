package domain

var reviewRules = []struct {
	text  string
	match func(a Applicant) bool
}{
	{
		text: "Стаж работы менее 1 года - обязательная ручная проверка",
		match: func(a Applicant) bool {
			return *a.Job != JobUnemployed && *a.EmploymentMonths < 12
		},
	},
	{
		text:  "Заёмщик не трудоустроен - обязательная ручная проверка",
		match: func(a Applicant) bool { return *a.Job == JobUnemployed },
	},
	{
		text: "Просрочки или критическая кредитная история - обязательная ручная проверка",
		match: func(a Applicant) bool {
			return *a.CreditHistory == CreditHistoryDelayed || *a.CreditHistory == CreditHistoryCritical
		},
	},
	{
		text:  "Платёж превышает 50% располагаемого дохода - обязательная ручная проверка",
		match: func(a Applicant) bool { return *a.InstallmentRate > 50 },
	},
	{
		text:  "Возраст заёмщика менее 21 года - обязательная ручная проверка",
		match: func(a Applicant) bool { return *a.Age < 21 },
	},
}

func Score(a Applicant, defaultProbability float64, t Thresholds) Scoring {
	s := Scoring{
		DefaultProbability: defaultProbability,
		Thresholds:         t,
		TriggeredRules:     []string{},
	}

	switch {
	case defaultProbability < t.Approve:
		s.Risk, s.Recommendation = RiskLow, RecommendationApprove
	case defaultProbability > t.Reject:
		s.Risk, s.Recommendation = RiskHigh, RecommendationReject
	default:
		s.Risk, s.Recommendation = RiskMedium, RecommendationReview
	}

	for _, rule := range reviewRules {
		if rule.match(a) {
			s.TriggeredRules = append(s.TriggeredRules, rule.text)
			if s.Recommendation == RecommendationApprove {
				s.Recommendation = RecommendationReview
			}
		}
	}
	return s
}

func StatusFor(r Recommendation) Status {
	if r == RecommendationReview {
		return StatusManualReview
	}
	return StatusNew
}
