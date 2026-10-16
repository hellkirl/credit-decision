package commands

import (
	"context"
	"fmt"

	"github.com/hellkirl/credit-decision/internal/domain"
	"github.com/hellkirl/credit-decision/internal/ports"
)

type UpdateApplication struct {
	ApplicationID int64
	Draft         bool
	Applicant     domain.Applicant
}

type UpdateApplicationHandler struct {
	repo    ports.ApplicationRepository
	scoring scoring
}

func NewUpdateApplicationHandler(repo ports.ApplicationRepository, scorer Scorer, approveThreshold float64) *UpdateApplicationHandler {
	return &UpdateApplicationHandler{
		repo:    repo,
		scoring: scoring{scorer: scorer, approveThreshold: approveThreshold},
	}
}

func (h *UpdateApplicationHandler) Handle(ctx context.Context, cmd UpdateApplication) error {
	app, err := h.repo.ByID(ctx, cmd.ApplicationID)
	if err != nil {
		return err
	}
	if err := app.Edit(cmd.Applicant, cmd.Draft); err != nil {
		return err
	}

	if !cmd.Draft {
		s, err := h.scoring.score(ctx, app.Applicant)
		if err != nil {
			return err
		}
		app.ApplyScoring(s)
	}

	if err := h.repo.Update(ctx, app); err != nil {
		return fmt.Errorf("update application: %w", err)
	}
	return nil
}
