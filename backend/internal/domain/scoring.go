package domain

func ScoreFromML(defaultProbability *float64, recommendation Recommendation, triggeredRules []string, t Thresholds) Scoring {
	if defaultProbability == nil {
		recommendation = RecommendationReview
	}

	risk := RiskMedium
	if defaultProbability != nil {
		switch {
		case *defaultProbability < t.Approve:
			risk = RiskLow
		case *defaultProbability > t.Reject:
			risk = RiskHigh
		}
	}

	return Scoring{
		DefaultProbability: defaultProbability,
		Thresholds:         t,
		Risk:               risk,
		Recommendation:     recommendation,
		TriggeredRules:     append([]string(nil), triggeredRules...),
	}
}

func StatusFor(r Recommendation) Status {
	if r == RecommendationReview {
		return StatusManualReview
	}
	return StatusNew
}
