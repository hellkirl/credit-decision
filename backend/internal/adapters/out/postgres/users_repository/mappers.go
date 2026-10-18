package usersrepository

import "github.com/hellkirl/credit-decision/internal/domain"

func toDomain(d UserDTO) *domain.User {
	return &domain.User{
		ID:           d.ID,
		Login:        d.Login,
		PasswordHash: d.PasswordHash,
		FullName:     d.FullName,
		Position:     d.Position,
	}
}

func toDTO(u *domain.User) UserDTO {
	return UserDTO{
		ID:           u.ID,
		Login:        u.Login,
		PasswordHash: u.PasswordHash,
		FullName:     u.FullName,
		Position:     u.Position,
	}
}
