package http

import (
	"context"
	"errors"
	"strconv"

	"github.com/hellkirl/credit-decision/internal/application/commands"
	"github.com/hellkirl/credit-decision/internal/application/queries"
	"github.com/hellkirl/credit-decision/internal/domain"
	genhttp "github.com/hellkirl/credit-decision/pkg/generated/http"
)

type Handlers struct {
	CreateApplication *commands.CreateApplicationHandler
	UpdateApplication *commands.UpdateApplicationHandler
	DeleteApplication *commands.DeleteApplicationHandler
	SaveDecision      *commands.SaveDecisionHandler
	Login             *commands.LoginHandler
	ListApplications  *queries.ListApplicationsHandler
	GetApplication    *queries.GetApplicationHandler
	GetStats          *queries.GetStatsHandler
	GetCurrentUser    *queries.GetCurrentUserHandler
}

type Server struct{ h Handlers }

var _ genhttp.StrictServerInterface = (*Server)(nil)

func NewServer(h Handlers) *Server { return &Server{h: h} }

func (s *Server) Health(context.Context, genhttp.HealthRequestObject) (genhttp.HealthResponseObject, error) {
	return genhttp.Health200JSONResponse{Status: genhttp.Ok}, nil
}

func (s *Server) Login(ctx context.Context, req genhttp.LoginRequestObject) (genhttp.LoginResponseObject, error) {
	token, err := s.h.Login.Handle(ctx, commands.Login{Login: req.Body.Login, Password: req.Body.Password})
	var verr *domain.ValidationError
	switch {
	case errors.As(err, &verr):
		return genhttp.Login400JSONResponse{BadRequestJSONResponse: badRequest(verr)}, nil
	case errors.Is(err, domain.ErrInvalidCredentials):
		return genhttp.Login401JSONResponse{Error: "invalid login or password"}, nil
	case err != nil:
		return nil, err
	}
	return genhttp.Login200JSONResponse{
		AccessToken: token.AccessToken,
		TokenType:   genhttp.Bearer,
		ExpiresIn:   int(token.TTL.Seconds()),
	}, nil
}

func (s *Server) GetCurrentUser(ctx context.Context, _ genhttp.GetCurrentUserRequestObject) (genhttp.GetCurrentUserResponseObject, error) {
	user, err := s.h.GetCurrentUser.Handle(ctx, userID(ctx))
	if errors.Is(err, domain.ErrNotFound) {
		return genhttp.GetCurrentUser401JSONResponse{UnauthorizedJSONResponse: unauthorized("user no longer exists")}, nil
	}
	if err != nil {
		return nil, err
	}
	return genhttp.GetCurrentUser200JSONResponse{Id: user.ID, FullName: user.FullName, Position: user.Position}, nil
}

func (s *Server) ListApplications(ctx context.Context, req genhttp.ListApplicationsRequestObject) (genhttp.ListApplicationsResponseObject, error) {
	p := req.Params
	q := queries.ListApplications{
		Status:         (*domain.Status)(p.Status),
		Risk:           (*domain.Risk)(p.Risk),
		Recommendation: (*domain.Recommendation)(p.Recommendation),
	}
	if p.Search != nil {
		q.Search = *p.Search
	}
	if p.Page != nil {
		q.Page = *p.Page
		if q.Page == 0 {
			q.Page = -1
		}
	}
	if p.PageSize != nil {
		q.PageSize = *p.PageSize
		if q.PageSize == 0 {
			q.PageSize = -1
		}
	}

	page, err := s.h.ListApplications.Handle(ctx, q)
	var verr *domain.ValidationError
	if errors.As(err, &verr) {
		return genhttp.ListApplications400JSONResponse{BadRequestJSONResponse: badRequest(verr)}, nil
	}
	if err != nil {
		return nil, err
	}

	items := make([]genhttp.ApplicationSummary, len(page.Items))
	for i, app := range page.Items {
		items[i] = toSummary(app)
	}
	return genhttp.ListApplications200JSONResponse{
		Items:    items,
		Total:    page.Total,
		Page:     page.Page,
		PageSize: page.PageSize,
	}, nil
}

func (s *Server) CreateApplication(ctx context.Context, req genhttp.CreateApplicationRequestObject) (genhttp.CreateApplicationResponseObject, error) {
	id, err := s.h.CreateApplication.Handle(ctx, commands.CreateApplication{
		Draft:     req.Body.Draft,
		Applicant: fromInput(*req.Body),
		UserID:    userID(ctx),
	})
	var verr *domain.ValidationError
	if errors.As(err, &verr) {
		return genhttp.CreateApplication400JSONResponse{BadRequestJSONResponse: badRequest(verr)}, nil
	}
	if err != nil {
		return nil, err
	}
	return genhttp.CreateApplication201JSONResponse{
		Body:    genhttp.CreatedResponse{Id: id},
		Headers: genhttp.CreateApplication201ResponseHeaders{Location: "/applications/" + strconv.FormatInt(id, 10)},
	}, nil
}

func (s *Server) GetApplicationsStats(ctx context.Context, _ genhttp.GetApplicationsStatsRequestObject) (genhttp.GetApplicationsStatsResponseObject, error) {
	st, err := s.h.GetStats.Handle(ctx)
	if err != nil {
		return nil, err
	}
	return genhttp.GetApplicationsStats200JSONResponse{
		Total:        st.Total,
		New:          st.New,
		ManualReview: st.ManualReview,
		Approved:     st.Approved,
		Rejected:     st.Rejected,
	}, nil
}

func (s *Server) GetApplication(ctx context.Context, req genhttp.GetApplicationRequestObject) (genhttp.GetApplicationResponseObject, error) {
	if req.Id < 1 {
		return genhttp.GetApplication400JSONResponse{BadRequestJSONResponse: genhttp.BadRequestJSONResponse{
			Error: "id must be a positive integer",
		}}, nil
	}
	app, err := s.h.GetApplication.Handle(ctx, req.Id)
	if errors.Is(err, domain.ErrNotFound) {
		return genhttp.GetApplication404JSONResponse{NotFoundJSONResponse: notFound}, nil
	}
	if err != nil {
		return nil, err
	}
	return genhttp.GetApplication200JSONResponse(toDetail(app)), nil
}

func (s *Server) SaveDecision(ctx context.Context, req genhttp.SaveDecisionRequestObject) (genhttp.SaveDecisionResponseObject, error) {
	err := s.h.SaveDecision.Handle(ctx, commands.SaveDecision{
		ApplicationID: req.Id,
		Decision:      domain.Decision(req.Body.Decision),
		Reason:        req.Body.Reason,
		UserID:        userID(ctx),
	})
	var verr *domain.ValidationError
	switch {
	case errors.As(err, &verr):
		return genhttp.SaveDecision400JSONResponse{BadRequestJSONResponse: badRequest(verr)}, nil
	case errors.Is(err, domain.ErrNotFound):
		return genhttp.SaveDecision404JSONResponse{NotFoundJSONResponse: notFound}, nil
	case errors.Is(err, domain.ErrDraftDecision):
		return genhttp.SaveDecision409JSONResponse{Error: "draft applications cannot be decided"}, nil
	case err != nil:
		return nil, err
	}
	return genhttp.SaveDecision204Response{}, nil
}

var notFound = genhttp.NotFoundJSONResponse{Error: "application not found"}

func badRequest(verr *domain.ValidationError) genhttp.BadRequestJSONResponse {
	fields := verr.Fields
	return genhttp.BadRequestJSONResponse{Error: "validation failed", Fields: &fields}
}

func unauthorized(msg string) genhttp.UnauthorizedJSONResponse {
	return genhttp.UnauthorizedJSONResponse{
		Body:    genhttp.Error{Error: msg},
		Headers: genhttp.UnauthorizedResponseHeaders{WWWAuthenticate: `Bearer error="invalid_token"`},
	}
}

func (s *Server) UpdateApplication(ctx context.Context, req genhttp.UpdateApplicationRequestObject) (genhttp.UpdateApplicationResponseObject, error) {
	err := s.h.UpdateApplication.Handle(ctx, commands.UpdateApplication{
		ApplicationID: req.Id,
		Draft:         req.Body.Draft,
		Applicant:     fromInput(*req.Body),
	})
	var verr *domain.ValidationError
	switch {
	case errors.As(err, &verr):
		return genhttp.UpdateApplication400JSONResponse{BadRequestJSONResponse: badRequest(verr)}, nil
	case errors.Is(err, domain.ErrNotFound):
		return genhttp.UpdateApplication404JSONResponse{NotFoundJSONResponse: notFound}, nil
	case errors.Is(err, domain.ErrCompletedEdit), errors.Is(err, domain.ErrRevertToDraft):
		return genhttp.UpdateApplication409JSONResponse{Error: err.Error()}, nil
	case err != nil:
		return nil, err
	}
	return genhttp.UpdateApplication204Response{}, nil
}

func (s *Server) DeleteApplication(ctx context.Context, req genhttp.DeleteApplicationRequestObject) (genhttp.DeleteApplicationResponseObject, error) {
	err := s.h.DeleteApplication.Handle(ctx, req.Id)
	switch {
	case errors.Is(err, domain.ErrNotFound):
		return genhttp.DeleteApplication404JSONResponse{NotFoundJSONResponse: notFound}, nil
	case errors.Is(err, domain.ErrNotDraft):
		return genhttp.DeleteApplication409JSONResponse{Error: err.Error()}, nil
	case err != nil:
		return nil, err
	}
	return genhttp.DeleteApplication204Response{}, nil
}
