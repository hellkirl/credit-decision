package commands

import (
	"context"
	"time"

	"github.com/hellkirl/credit-decision/internal/domain"
	"github.com/hellkirl/credit-decision/internal/ports"
)

type SaveDecision struct {
	ApplicationID int64
	Decision      domain.Decision
	Reason        string
	UserID        int64
}

type SaveDecisionHandler struct {
	repo ports.ApplicationRepository
	now  func() time.Time
}

func NewSaveDecisionHandler(repo ports.ApplicationRepository) *SaveDecisionHandler {
	return &SaveDecisionHandler{repo: repo, now: time.Now}
}

func (h *SaveDecisionHandler) Handle(ctx context.Context, cmd SaveDecision) error {
	decision, err := domain.NewDecision(cmd.Decision, cmd.Reason, cmd.UserID, h.now().UTC())
	if err != nil {
		return err
	}
	app, err := h.repo.ByID(ctx, cmd.ApplicationID)
	if err != nil {
		return err
	}
	if err := app.Decide(decision); err != nil {
		return err
	}
	return h.repo.Update(ctx, app)
}
