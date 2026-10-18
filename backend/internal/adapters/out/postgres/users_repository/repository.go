package usersrepository

import (
	"context"
	"errors"

	"gorm.io/gorm"

	"github.com/hellkirl/credit-decision/internal/domain"
	"github.com/hellkirl/credit-decision/internal/ports"
)

var _ ports.UserRepository = &Repository{}

type Repository struct {
	db *gorm.DB
}

func New(db *gorm.DB) *Repository {
	return &Repository{db: db}
}

func (r *Repository) ByLogin(ctx context.Context, login string) (*domain.User, error) {
	return r.first(r.db.WithContext(ctx).Where("lower(login) = lower(?)", login))
}

func (r *Repository) ByID(ctx context.Context, id int64) (*domain.User, error) {
	return r.first(r.db.WithContext(ctx).Where("id = ?", id))
}

func (r *Repository) Upsert(ctx context.Context, u *domain.User) error {
	return r.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		var existing UserDTO
		err := tx.Where("lower(login) = lower(?)", u.Login).First(&existing).Error
		if errors.Is(err, gorm.ErrRecordNotFound) {
			dto := toDTO(u)
			if err := tx.Create(&dto).Error; err != nil {
				return err
			}
			u.ID = dto.ID
			return nil
		}
		if err != nil {
			return err
		}
		u.ID = existing.ID
		return tx.Model(&existing).Updates(map[string]any{
			"password_hash": u.PasswordHash,
			"full_name":     u.FullName,
			"position":      u.Position,
		}).Error
	})
}

func (r *Repository) first(q *gorm.DB) (*domain.User, error) {
	var dto UserDTO
	err := q.First(&dto).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, domain.ErrNotFound
	}
	if err != nil {
		return nil, err
	}
	return toDomain(dto), nil
}
