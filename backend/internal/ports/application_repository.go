package ports

import (
	"context"

	"github.com/hellkirl/credit-decision/internal/domain"
)

type ApplicationRepository interface {
	Create(ctx context.Context, app *domain.Application) (int64, error)
	ByID(ctx context.Context, id int64) (*domain.Application, error)
	Update(ctx context.Context, app *domain.Application) error
	List(ctx context.Context, f domain.ApplicationFilter) ([]domain.Application, int, error)
	Stats(ctx context.Context) (domain.ApplicationStats, error)
	DeleteDraft(ctx context.Context, id int64) error
}
