package domain

type ApplicationFilter struct {
	ID             *int64
	Borrower       string
	Status         *Status
	Risk           *Risk
	Recommendation *Recommendation
	Limit          int
	Offset         int
}

type ApplicationStats struct {
	Total        int
	New          int
	ManualReview int
	Approved     int
	Rejected     int
}
