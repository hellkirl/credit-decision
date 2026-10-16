APP_NAME=credit-decision
GO_TOOLCHAIN?=go1.27.1
ML_PYTHON?=ml/venv/bin/python

.PHONY: generate ml-openapi

generate:
	@mkdir -p backend/pkg/generated/ml
	@oapi-codegen --config=backend/oapi-codegen.yaml backend/api/openapi/openapi.yaml
	@oapi-codegen --config=backend/oapi-codegen.ml.yaml backend/api/openapi/ml.json
	@cd frontend && npm run --silent api:types

ml-openapi:
	@$(ML_PYTHON) ml/scripts/export_openapi.py backend/api/openapi/ml.json
