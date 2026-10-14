from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.ml.inference import load_classifier

MODEL_PATH = Path(__file__).resolve().parent / "models" / "waste_classifier.joblib"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the saved EcoSort waste classifier on one image."
    )
    parser.add_argument("image", type=Path)
    parser.add_argument("--model", type=Path, default=MODEL_PATH)
    args = parser.parse_args()
    prediction = load_classifier(args.model).predict(args.image.read_bytes())
    print(json.dumps(prediction, indent=2))


if __name__ == "__main__":
    main()
