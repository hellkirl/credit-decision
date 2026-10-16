package commands

import (
	"context"
	"fmt"
	"math/rand/v2"
	"time"

	"github.com/hellkirl/credit-decision/internal/domain"
	"github.com/hellkirl/credit-decision/internal/ports"
)

type Prediction struct {
	DefaultProbability float64
	RejectThreshold    float64
}

type Scorer interface {
	Predict(ctx context.Context, a domain.Applicant) (Prediction, error)
}

type scoring struct {
	scorer           Scorer
	approveThreshold float64
}

func (s scoring) score(ctx context.Context, a domain.Applicant) (domain.Scoring, error) {
	p, err := s.scorer.Predict(ctx, a)
	if err != nil {
		return domain.Scoring{}, fmt.Errorf("score application: %w", err)
	}
	thresholds := domain.Thresholds{
		Approve: min(s.approveThreshold, p.RejectThreshold),
		Reject:  p.RejectThreshold,
	}
	return domain.Score(a, p.DefaultProbability, thresholds), nil
}

type CreateApplication struct {
	Draft     bool
	Applicant domain.Applicant
	UserID    int64
}

type CreateApplicationHandler struct {
	repo    ports.ApplicationRepository
	scoring scoring
	now     func() time.Time
}

func NewCreateApplicationHandler(repo ports.ApplicationRepository, scorer Scorer, approveThreshold float64) *CreateApplicationHandler {
	return &CreateApplicationHandler{
		repo:    repo,
		scoring: scoring{scorer: scorer, approveThreshold: approveThreshold},
		now:     time.Now,
	}
}

func (h *CreateApplicationHandler) Handle(ctx context.Context, cmd CreateApplication) (int64, error) {
	app := &domain.Application{
		ClientID:  newClientID(),
		Status:    domain.StatusDraft,
		CreatedBy: cmd.UserID,
		CreatedAt: h.now().UTC(),
	}
	if err := app.Edit(cmd.Applicant, cmd.Draft); err != nil {
		return 0, err
	}

	if !cmd.Draft {
		s, err := h.scoring.score(ctx, app.Applicant)
		if err != nil {
			return 0, err
		}
		app.ApplyScoring(s)
	}

	id, err := h.repo.Create(ctx, app)
	if err != nil {
		return 0, fmt.Errorf("create application: %w", err)
	}
	return id, nil
}

func newClientID() string {
	return fmt.Sprintf("%03d-%02d-%02d", rand.IntN(1000), rand.IntN(100), rand.IntN(100))
}
