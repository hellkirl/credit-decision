package queries

import (
	"context"
	"strconv"
	"strings"

	"github.com/hellkirl/credit-decision/internal/domain"
	"github.com/hellkirl/credit-decision/internal/ports"
)

type ListApplications struct {
	Search         string
	Status         *domain.Status
	Risk           *domain.Risk
	Recommendation *domain.Recommendation
	Page           int
	PageSize       int
}

type ApplicationsPage struct {
	Items    []domain.Application
	Total    int
	Page     int
	PageSize int
}

const (
	defaultPageSize = 12
	maxPageSize     = 100
)

type ListApplicationsHandler struct{ repo ports.ApplicationRepository }

func NewListApplicationsHandler(repo ports.ApplicationRepository) *ListApplicationsHandler {
	return &ListApplicationsHandler{repo: repo}
}

func (h *ListApplicationsHandler) Handle(ctx context.Context, q ListApplications) (ApplicationsPage, error) {
	v := map[string]string{}
	if q.Page == 0 {
		q.Page = 1
	}
	if q.PageSize == 0 {
		q.PageSize = defaultPageSize
	}
	if q.Page < 1 {
		v["page"] = "must be at least 1"
	}
	if q.PageSize < 1 || q.PageSize > maxPageSize {
		v["page_size"] = "must be between 1 and 100"
	}
	if q.Status != nil && !q.Status.Valid() {
		v["status"] = "has an unknown value"
	}
	if q.Risk != nil && !q.Risk.Valid() {
		v["risk"] = "has an unknown value"
	}
	if q.Recommendation != nil && !q.Recommendation.Valid() {
		v["recommendation"] = "has an unknown value"
	}
	if len(v) > 0 {
		return ApplicationsPage{}, &domain.ValidationError{Fields: v}
	}

	f := domain.ApplicationFilter{
		Status:         q.Status,
		Risk:           q.Risk,
		Recommendation: q.Recommendation,
		Limit:          q.PageSize,
		Offset:         (q.Page - 1) * q.PageSize,
	}
	search := strings.TrimSpace(q.Search)
	if id, err := strconv.ParseInt(strings.TrimPrefix(search, "#"), 10, 64); err == nil {
		f.ID = &id
	} else {
		f.Borrower = search
	}

	items, total, err := h.repo.List(ctx, f)
	if err != nil {
		return ApplicationsPage{}, err
	}
	return ApplicationsPage{Items: items, Total: total, Page: q.Page, PageSize: q.PageSize}, nil
}

type GetApplicationHandler struct{ repo ports.ApplicationRepository }

func NewGetApplicationHandler(repo ports.ApplicationRepository) *GetApplicationHandler {
	return &GetApplicationHandler{repo: repo}
}

func (h *GetApplicationHandler) Handle(ctx context.Context, id int64) (domain.Application, error) {
	app, err := h.repo.ByID(ctx, id)
	if err != nil {
		return domain.Application{}, err
	}
	return *app, nil
}

type GetStatsHandler struct{ repo ports.ApplicationRepository }

func NewGetStatsHandler(repo ports.ApplicationRepository) *GetStatsHandler {
	return &GetStatsHandler{repo: repo}
}

func (h *GetStatsHandler) Handle(ctx context.Context) (domain.ApplicationStats, error) {
	return h.repo.Stats(ctx)
}
