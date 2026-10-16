package domain

import (
	"errors"
	"sort"
	"strings"
)

var (
	ErrNotFound           = errors.New("not found")
	ErrDraftDecision      = errors.New("draft application cannot be decided")
	ErrInvalidCredentials = errors.New("invalid login or password")
	ErrUnauthorized       = errors.New("unauthorized")
	ErrNotDraft           = errors.New("only drafts can be deleted")
	ErrCompletedEdit      = errors.New("completed application cannot be edited")
	ErrRevertToDraft      = errors.New("submitted application cannot become a draft")
)

type ValidationError struct {
	Fields map[string]string
}

func (e *ValidationError) Error() string {
	keys := make([]string, 0, len(e.Fields))
	for k := range e.Fields {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	parts := make([]string, len(keys))
	for i, k := range keys {
		parts[i] = k + ": " + e.Fields[k]
	}
	return "validation failed: " + strings.Join(parts, "; ")
}

type validator map[string]string

func (v validator) add(field, msg string) {
	if _, exists := v[field]; !exists {
		v[field] = msg
	}
}

func (v validator) err() error {
	if len(v) == 0 {
		return nil
	}
	return &ValidationError{Fields: v}
}
