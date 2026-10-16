package queries

import (
	"context"

	"github.com/hellkirl/credit-decision/internal/domain"
	"github.com/hellkirl/credit-decision/internal/ports"
)

type GetCurrentUserHandler struct{ users ports.UserRepository }

func NewGetCurrentUserHandler(users ports.UserRepository) *GetCurrentUserHandler {
	return &GetCurrentUserHandler{users: users}
}

func (h *GetCurrentUserHandler) Handle(ctx context.Context, userID int64) (domain.User, error) {
	u, err := h.users.ByID(ctx, userID)
	if err != nil {
		return domain.User{}, err
	}
	return *u, nil
}
