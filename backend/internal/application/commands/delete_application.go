package commands

import (
	"context"

	"github.com/hellkirl/credit-decision/internal/ports"
)

type DeleteApplicationHandler struct {
	repo ports.ApplicationRepository
}

func NewDeleteApplicationHandler(repo ports.ApplicationRepository) *DeleteApplicationHandler {
	return &DeleteApplicationHandler{repo: repo}
}

func (h *DeleteApplicationHandler) Handle(ctx context.Context, id int64) error {
	app, err := h.repo.ByID(ctx, id)
	if err != nil {
		return err
	}
	if err := app.EnsureDeletable(); err != nil {
		return err
	}
	return h.repo.DeleteDraft(ctx, id)
}
