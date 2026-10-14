from __future__ import annotations

import pickle
from io import BytesIO
from pathlib import Path
from typing import Any, cast

import joblib
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from skimage.color import rgb2gray
from skimage.feature import hog

IMAGE_SIZE = (64, 64)
MODEL_VERSION = "waste-hog-logistic-v1"
CLASS_CATEGORY_MAP = {
    "O": "Wet Waste",
    "R": "Dry Waste",
}


class InvalidImageError(ValueError):
    pass


class InferenceError(RuntimeError):
    pass


class ModelArtifactError(RuntimeError):
    pass


def image_features(image_bytes: bytes) -> np.ndarray:
    try:
        with Image.open(BytesIO(image_bytes)) as source:
            source.load()
            image = ImageOps.fit(
                source.convert("RGB"),
                IMAGE_SIZE,
                method=Image.Resampling.BILINEAR,
            )
    except (
        Image.DecompressionBombError,
        OSError,
        UnidentifiedImageError,
        ValueError,
    ) as exc:
        raise InvalidImageError("The uploaded bytes are not a readable image.") from exc

    rgb = np.asarray(image, dtype=np.uint8)
    grayscale = rgb2gray(rgb)
    shape_features = hog(
        grayscale,
        orientations=9,
        pixels_per_cell=(8, 8),
        cells_per_block=(2, 2),
        transform_sqrt=True,
        feature_vector=True,
    ).astype(np.float32, copy=False)
    color_features, _ = np.histogramdd(
        rgb.reshape(-1, 3),
        bins=(8, 8, 8),
        range=((0, 256), (0, 256), (0, 256)),
    )
    color_features = (color_features / color_features.sum()).astype(
        np.float32, copy=False
    )
    return np.concatenate((shape_features, color_features.ravel()))


class WasteImageClassifier:
    def __init__(
        self,
        estimator: Any,
        model_version: str,
        classes: list[str],
    ) -> None:
        self.estimator = estimator
        self.model_version = model_version
        self.classes = classes

    def predict(self, image_bytes: bytes) -> dict[str, str | float]:
        features = image_features(image_bytes)
        try:
            probabilities = self.estimator.predict_proba(features.reshape(1, -1))[0]
        except (AttributeError, IndexError, RuntimeError, TypeError, ValueError) as exc:
            raise InferenceError("The trained model could not predict this image.") from exc

        best_index = int(np.argmax(probabilities))
        dataset_label = self.classes[best_index]
        return {
            "category": CLASS_CATEGORY_MAP[dataset_label],
            "confidence": float(probabilities[best_index]),
            "model_version": self.model_version,
        }


def load_classifier(model_path: Path) -> WasteImageClassifier:
    if not model_path.is_file():
        raise FileNotFoundError(model_path)

    try:
        bundle = joblib.load(model_path)
        if not isinstance(bundle, dict):
            raise ValueError("The model artifact must be a dictionary.")
        estimator = bundle["estimator"]
        model_version = bundle["model_version"]
        classes = bundle["classes"]
        if (
            not hasattr(estimator, "predict_proba")
            or not isinstance(model_version, str)
            or not isinstance(classes, list)
            or not classes
            or not all(isinstance(label, str) for label in classes)
            or set(classes) != set(CLASS_CATEGORY_MAP)
            or list(estimator.classes_) != classes
        ):
            raise ValueError("The model artifact has an invalid classifier payload.")
    except (
        AttributeError,
        EOFError,
        ImportError,
        KeyError,
        OSError,
        pickle.UnpicklingError,
        TypeError,
        ValueError,
    ) as exc:
        raise ModelArtifactError("The classifier model artifact is invalid.") from exc

    return WasteImageClassifier(
        estimator=cast(Any, estimator),
        model_version=model_version,
        classes=classes,
    )
