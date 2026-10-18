package applicationsrepository

import (
	"time"

	"github.com/lib/pq"

	usersrepository "github.com/hellkirl/credit-decision/internal/adapters/out/postgres/users_repository"
)

type ApplicationDTO struct {
	ID        int64     `gorm:"primaryKey;index:applications_created_at_idx,sort:desc,priority:2"`
	ClientID  string    `gorm:"not null"`
	Status    string    `gorm:"not null;index;check:status IN ('draft', 'new', 'manual_review', 'pending_confirmation', 'completed')"`
	CreatedBy int64     `gorm:"not null"`
	CreatedAt time.Time `gorm:"not null;index:applications_created_at_idx,sort:desc,priority:1"`

	Borrower              *string
	Dependents            *int
	Housing               *string
	Age                   *int
	Phone                 *bool
	ResidenceYears        *int
	MaritalStatus         *string
	ForeignWorker         *bool
	Property              *string
	Job                   *string
	EmploymentMonths      *int
	Amount                *int64
	TermMonths            *int
	Purpose               *string
	InstallmentRate       *float64
	CheckingStatus        *string
	OtherInstallmentPlans *bool
	Savings               *string
	OtherDebtors          *bool
	CreditHistory         *string
	ExistingCredits       *int

	DefaultProbability *float64 `gorm:"check:applications_scored_unless_draft,(status = 'draft') = (default_probability IS NULL)"`
	ApproveThreshold   *float64
	RejectThreshold    *float64
	Risk               *string        `gorm:"check:risk IN ('low', 'medium', 'high')"`
	Recommendation     *string        `gorm:"check:recommendation IN ('approve', 'review', 'reject')"`
	TriggeredRules     pq.StringArray `gorm:"type:text[];not null;default:'{}'"`

	Decision       *string `gorm:"check:decision IN ('approve', 'reject')"`
	DecisionReason *string `gorm:"check:applications_decision_complete,(decision IS NULL) = (decision_reason IS NULL)"`
	DecidedBy      *int64
	DecidedAt      *time.Time

	Creator *usersrepository.UserDTO `gorm:"foreignKey:CreatedBy"`
	Decider *usersrepository.UserDTO `gorm:"foreignKey:DecidedBy"`
}

func (ApplicationDTO) TableName() string { return "applications" }
