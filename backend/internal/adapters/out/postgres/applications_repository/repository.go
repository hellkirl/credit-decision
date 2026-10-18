package applicationsrepository

import (
	"context"
	"errors"
	"strings"

	"gorm.io/gorm"
	"gorm.io/gorm/clause"

	"github.com/hellkirl/credit-decision/internal/domain"
	"github.com/hellkirl/credit-decision/internal/ports"
)

var _ ports.ApplicationRepository = &Repository{}

type Repository struct {
	db *gorm.DB
}

func New(db *gorm.DB) *Repository {
	return &Repository{db: db}
}

func (r *Repository) Create(ctx context.Context, app *domain.Application) (int64, error) {
	dto := toDTO(app)
	if err := r.db.WithContext(ctx).Omit(clause.Associations).Create(&dto).Error; err != nil {
		return 0, err
	}
	app.ID = dto.ID
	return dto.ID, nil
}

func (r *Repository) ByID(ctx context.Context, id int64) (*domain.Application, error) {
	var dto ApplicationDTO
	err := r.db.WithContext(ctx).First(&dto, id).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, domain.ErrNotFound
	}
	if err != nil {
		return nil, err
	}
	return toDomain(dto), nil
}

func (r *Repository) Update(ctx context.Context, app *domain.Application) error {
	dto := toDTO(app)
	res := r.db.WithContext(ctx).
		Model(&ApplicationDTO{}).
		Where("id = ?", app.ID).
		Select("*").
		Omit("id", "created_by", "created_at", clause.Associations).
		Updates(&dto)
	if res.Error != nil {
		return res.Error
	}
	if res.RowsAffected == 0 {
		return domain.ErrNotFound
	}
	return nil
}

func (r *Repository) List(ctx context.Context, f domain.ApplicationFilter) ([]domain.Application, int, error) {
	q := r.db.WithContext(ctx).Model(&ApplicationDTO{})
	if f.ID != nil {
		q = q.Where("id = ?", *f.ID)
	}
	if f.Borrower != "" {
		q = q.Where("borrower ILIKE ?", "%"+escapeLike(f.Borrower)+"%")
	}
	if f.Status != nil {
		q = q.Where("status = ?", string(*f.Status))
	}
	if f.Risk != nil {
		q = q.Where("risk = ?", string(*f.Risk))
	}
	if f.Recommendation != nil {
		q = q.Where("recommendation = ?", string(*f.Recommendation))
	}

	var total int64
	if err := q.Count(&total).Error; err != nil {
		return nil, 0, err
	}

	var dtos []ApplicationDTO
	if err := q.Order("created_at DESC, id DESC").Limit(f.Limit).Offset(f.Offset).Find(&dtos).Error; err != nil {
		return nil, 0, err
	}

	items := make([]domain.Application, len(dtos))
	for i, d := range dtos {
		items[i] = *toDomain(d)
	}
	return items, int(total), nil
}

func (r *Repository) Stats(ctx context.Context) (domain.ApplicationStats, error) {
	var s domain.ApplicationStats
	err := r.db.WithContext(ctx).Model(&ApplicationDTO{}).Select(`
		count(*) FILTER (WHERE status <> 'draft') AS total,
		count(*) FILTER (WHERE status = 'new') AS new,
		count(*) FILTER (WHERE status = 'manual_review') AS manual_review,
		count(*) FILTER (WHERE status = 'completed' AND decision = 'approve') AS approved,
		count(*) FILTER (WHERE status = 'completed' AND decision = 'reject') AS rejected`,
	).Scan(&s).Error
	return s, err
}

func escapeLike(s string) string {
	return strings.NewReplacer(`\`, `\\`, `%`, `\%`, `_`, `\_`).Replace(s)
}

func (r *Repository) DeleteDraft(ctx context.Context, id int64) error {
	res := r.db.WithContext(ctx).Where("id = ? AND status = ?", id, string(domain.StatusDraft)).Delete(&ApplicationDTO{})
	if res.Error != nil {
		return res.Error
	}
	if res.RowsAffected == 0 {
		return domain.ErrNotDraft
	}
	return nil
}
