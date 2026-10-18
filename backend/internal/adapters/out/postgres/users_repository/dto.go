package usersrepository

import "time"

type UserDTO struct {
	ID           int64  `gorm:"primaryKey"`
	Login        string `gorm:"not null;index:users_login_key,unique,expression:lower(login)"`
	PasswordHash string `gorm:"not null"`
	FullName     string `gorm:"not null"`
	Position     string `gorm:"not null"`
	CreatedAt    time.Time
}

func (UserDTO) TableName() string { return "users" }
