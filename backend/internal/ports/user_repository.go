package ports

import (
	"context"

	"github.com/hellkirl/credit-decision/internal/domain"
)

type UserRepository interface {
	ByLogin(ctx context.Context, login string) (*domain.User, error)
	ByID(ctx context.Context, id int64) (*domain.User, error)
	Upsert(ctx context.Context, u *domain.User) error
}
