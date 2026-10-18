from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DATA_PATH = PROJECT_ROOT / "data" / "raw" / "SouthGermanCredit.asc"
PROCESSED_DATA_PATH = PROJECT_ROOT / "data" / "processed" / "south_german_credit.csv"
MODEL_PATH = PROJECT_ROOT / "models" / "logistic_regression.joblib"
METADATA_PATH = PROJECT_ROOT / "models" / "training_metadata.json"
CALIBRATOR_PATH = PROJECT_ROOT / "models" / "platt_calibrator.joblib"
REPORTS_DIR = PROJECT_ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

COLUMN_RENAME = {
    "laufkont": "status",
    "laufzeit": "duration",
    "moral": "credit_history",
    "verw": "purpose",
    "hoehe": "amount",
    "sparkont": "savings",
    "beszeit": "employment_duration",
    "rate": "installment_rate",
    "famges": "personal_status_sex",
    "buerge": "other_debtors",
    "wohnzeit": "present_residence",
    "verm": "property",
    "alter": "age",
    "weitkred": "other_installment_plans",
    "wohn": "housing",
    "bishkred": "number_credits",
    "beruf": "job",
    "pers": "people_liable",
    "telef": "telephone",
    "gastarb": "foreign_worker",
    "kredit": "credit_risk",
}

TARGET = "credit_risk"

NUMERIC_FEATURES = ["duration", "amount", "age"]

ORDINAL_FEATURES = [
    "status",
    "credit_history",
    "savings",
    "employment_duration",
    "installment_rate",
    "present_residence",
    "property",
    "number_credits",
    "job",
]

CATEGORICAL_FEATURES = [
    "purpose",
    "personal_status_sex",
    "other_debtors",
    "other_installment_plans",
    "housing",
    "people_liable",
    "telephone",
    "foreign_worker",
]

FEATURE_COLUMNS = NUMERIC_FEATURES + ORDINAL_FEATURES + CATEGORICAL_FEATURES

RANDOM_STATE = 42
TEST_SIZE = 0.2
CV_FOLDS = 5
