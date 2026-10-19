package ml

import (
	"context"
	"fmt"
	"net/http"
	"time"

	"github.com/hellkirl/credit-decision/internal/application/commands"
	"github.com/hellkirl/credit-decision/internal/domain"
	genml "github.com/hellkirl/credit-decision/pkg/generated/ml"
)

type Client struct {
	api      genml.ClientWithResponsesInterface
	rubPerDM float64
}

func NewClient(baseURL string, timeout time.Duration, rubPerDM float64) (*Client, error) {
	api, err := genml.NewClientWithResponses(baseURL, genml.WithHTTPClient(&http.Client{Timeout: timeout}))
	if err != nil {
		return nil, fmt.Errorf("ml client: %w", err)
	}
	return &Client{api: api, rubPerDM: rubPerDM}, nil
}

func (c *Client) Predict(ctx context.Context, a domain.Applicant) (commands.Prediction, error) {
	features, err := toFeatures(a, c.rubPerDM)
	if err != nil {
		return commands.Prediction{}, err
	}

	resp, err := c.api.PredictWithResponse(ctx, features)
	if err != nil {
		return commands.Prediction{}, fmt.Errorf("ml predict: %w", err)
	}
	if resp.JSON200 == nil {
		return commands.Prediction{}, fmt.Errorf("ml predict: status %d: %.1024s", resp.StatusCode(), resp.Body)
	}

	recommendation := domain.Recommendation(resp.JSON200.Decision)
	if !recommendation.Valid() {
		return commands.Prediction{}, fmt.Errorf("ml predict: unsupported decision %q", recommendation)
	}
	triggeredRules := make([]string, 0)
	if resp.JSON200.Reasons != nil {
		for _, reason := range *resp.JSON200.Reasons {
			code := reason["code"]
			field := reason["field"]
			switch {
			case code != "" && field != "":
				triggeredRules = append(triggeredRules, code+": "+field)
			case code != "":
				triggeredRules = append(triggeredRules, code)
			case field != "":
				triggeredRules = append(triggeredRules, field)
			}
		}
	}

	return commands.Prediction{
		DefaultProbability: resp.JSON200.ProbabilityBad,
		Recommendation:     recommendation,
		TriggeredRules:     triggeredRules,
	}, nil
}
