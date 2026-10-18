package postgres

import (
	"context"
	"fmt"
	"log"
	"os"
	"time"

	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"

	applicationsrepository "github.com/hellkirl/credit-decision/internal/adapters/out/postgres/applications_repository"
	usersrepository "github.com/hellkirl/credit-decision/internal/adapters/out/postgres/users_repository"
)

const (
	migrationLockID    = 7_310_245
	firstApplicationID = 10001
)

func NewPostgresClient(dsn string) (*gorm.DB, error) {
	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{
		Logger: logger.New(log.New(os.Stderr, "", log.LstdFlags), logger.Config{
			SlowThreshold:             200 * time.Millisecond,
			LogLevel:                  logger.Warn,
			IgnoreRecordNotFoundError: true,
		}),
	})
	if err != nil {
		return nil, fmt.Errorf("open database: %w", err)
	}
	return db, nil
}

func Migrate(ctx context.Context, db *gorm.DB) error {
	return db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if err := tx.Exec("SELECT pg_advisory_xact_lock(?)", migrationLockID).Error; err != nil {
			return err
		}
		if err := tx.AutoMigrate(&usersrepository.UserDTO{}, &applicationsrepository.ApplicationDTO{}); err != nil {
			return fmt.Errorf("auto migrate: %w", err)
		}
		return tx.Exec(`SELECT setval(pg_get_serial_sequence('applications', 'id'),
			GREATEST(?, (SELECT COALESCE(MAX(id), 0) FROM applications)))`, firstApplicationID-1).Error
	})
}

func Close(db *gorm.DB) {
	if sqlDB, err := db.DB(); err == nil {
		_ = sqlDB.Close()
	}
}
