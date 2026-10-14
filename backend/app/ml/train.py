from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)
from sklearn.model_selection import train_test_split

from app.ml.inference import CLASS_CATEGORY_MAP, MODEL_VERSION, image_features

logger = logging.getLogger("app.ml.train")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
RANDOM_SEED = 42
VALIDATION_FRACTION = 0.15


@dataclass(frozen=True)
class ImagePath:
    path: Path
    label: str


@dataclass(frozen=True)
class ImageSample:
    path: Path
    label: str
    digest: str
    features: np.ndarray


def find_split_directory(root: Path, names: set[str]) -> Path | None:
    for child in root.iterdir():
        if child.is_dir() and child.name.casefold() in names:
            return child
    return None


def collect_class_directories(directory: Path) -> list[ImagePath]:
    classes = sorted(
        (child for child in directory.iterdir() if child.is_dir()),
        key=lambda child: child.name.casefold(),
    )
    if not classes:
        raise ValueError(f"No class subdirectories were found in {directory}.")

    paths = [
        ImagePath(path, class_dir.name)
        for class_dir in classes
        for path in sorted(class_dir.rglob("*"))
        if path.is_file() and path.suffix.casefold() in IMAGE_EXTENSIONS
    ]
    if not paths:
        raise ValueError(f"No supported images were found in {directory}.")
    return paths


def read_annotations(
    dataset_dir: Path,
    annotations_path: Path,
    image_column: str,
    label_column: str,
    split_column: str,
) -> dict[str, list[ImagePath]]:
    partitions: dict[str, list[ImagePath]] = {
        "train": [],
        "validation": [],
        "test": [],
        "unassigned": [],
    }
    split_names = {
        "train": "train",
        "training": "train",
        "val": "validation",
        "valid": "validation",
        "validation": "validation",
        "test": "test",
        "testing": "test",
    }

    with annotations_path.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        if not reader.fieldnames or image_column not in reader.fieldnames:
            raise ValueError(f"CSV is missing the image column {image_column!r}.")
        if label_column not in reader.fieldnames:
            raise ValueError(f"CSV is missing the label column {label_column!r}.")

        for row_number, row in enumerate(reader, start=2):
            image_value = (row.get(image_column) or "").strip()
            label = (row.get(label_column) or "").strip()
            if not image_value or not label:
                raise ValueError(f"CSV row {row_number} has an empty image or label.")

            image_path = Path(image_value)
            if not image_path.is_absolute():
                dataset_candidate = dataset_dir / image_path
                annotation_candidate = annotations_path.parent / image_path
                image_path = (
                    dataset_candidate
                    if dataset_candidate.is_file()
                    else annotation_candidate
                )
            if not image_path.is_file():
                raise ValueError(
                    f"CSV row {row_number} references missing image {image_path}."
                )

            raw_split = (row.get(split_column) or "").strip().casefold()
            partition = split_names.get(raw_split, "unassigned")
            if raw_split and partition == "unassigned":
                raise ValueError(
                    f"CSV row {row_number} has unsupported split {raw_split!r}."
                )
            partitions[partition].append(ImagePath(image_path, label))

    if not any(partitions.values()):
        raise ValueError(f"No image records were found in {annotations_path}.")
    return partitions


def discover_records(
    dataset_dir: Path,
    annotations_path: Path | None,
    image_column: str,
    label_column: str,
    split_column: str,
) -> tuple[dict[str, list[ImagePath]], str]:
    if annotations_path is not None:
        path = annotations_path.resolve()
        return (
            read_annotations(
                dataset_dir,
                path,
                image_column,
                label_column,
                split_column,
            ),
            "csv",
        )

    train_dir = find_split_directory(dataset_dir, {"train", "training"})
    test_dir = find_split_directory(dataset_dir, {"test", "testing"})
    validation_dir = find_split_directory(
        dataset_dir, {"validation", "valid", "val"}
    )
    if train_dir is not None:
        partitions = {
            "train": collect_class_directories(train_dir),
            "validation": (
                collect_class_directories(validation_dir)
                if validation_dir is not None
                else []
            ),
            "test": (
                collect_class_directories(test_dir) if test_dir is not None else []
            ),
            "unassigned": [],
        }
        return partitions, "class-folders-with-splits"

    return (
        {
            "train": [],
            "validation": [],
            "test": [],
            "unassigned": collect_class_directories(dataset_dir),
        },
        "class-folders",
    )


def extract_samples(
    records: list[ImagePath], skipped_images: list[str]
) -> list[ImageSample]:
    samples: list[ImageSample] = []
    for index, record in enumerate(records, start=1):
        try:
            payload = record.path.read_bytes()
            digest = hashlib.sha256(payload).hexdigest()
            features = image_features(payload)
        except (OSError, ValueError) as exc:
            skipped_images.append(str(record.path))
            logger.warning("Skipping unreadable image %s: %s", record.path, exc)
            continue
        samples.append(
            ImageSample(
                path=record.path,
                label=record.label,
                digest=digest,
                features=features,
            )
        )
        if index % 2000 == 0:
            logger.info("Extracted features for %d/%d images", index, len(records))
    return samples


def deduplicate_samples(
    samples: list[ImageSample],
    partition: str,
    blocked_digests: set[str] | None = None,
) -> tuple[list[ImageSample], int]:
    blocked = blocked_digests or set()
    seen: dict[str, str] = {}
    unique: list[ImageSample] = []
    removed = 0
    for sample in samples:
        if sample.digest in blocked:
            removed += 1
            continue
        previous_label = seen.get(sample.digest)
        if previous_label is not None:
            if previous_label != sample.label:
                raise ValueError(
                    "Identical image content has conflicting labels "
                    f"{previous_label!r} and {sample.label!r} in {partition}."
                )
            removed += 1
            continue
        seen[sample.digest] = sample.label
        unique.append(sample)
    return unique, removed


def split_samples(
    samples: list[ImageSample], test_size: float
) -> tuple[list[ImageSample], list[ImageSample]]:
    if len({sample.label for sample in samples}) < 2:
        raise ValueError("At least two classes are required for stratified splitting.")
    try:
        train, holdout = train_test_split(
            samples,
            test_size=test_size,
            random_state=RANDOM_SEED,
            stratify=[sample.label for sample in samples],
        )
    except ValueError as exc:
        raise ValueError(
            "The dataset is too small to create stratified train, validation, "
            "and test splits."
        ) from exc
    return list(train), list(holdout)


def sample_arrays(
    samples: list[ImageSample],
) -> tuple[np.ndarray, np.ndarray]:
    return (
        np.vstack([sample.features for sample in samples]),
        np.asarray([sample.label for sample in samples]),
    )


def make_classifier(alpha: float) -> SGDClassifier:
    return SGDClassifier(
        loss="log_loss",
        penalty="l2",
        alpha=alpha,
        class_weight="balanced",
        max_iter=1000,
        tol=1e-3,
        random_state=RANDOM_SEED,
    )


def metric_summary(
    expected: np.ndarray, predicted: np.ndarray, labels: list[str]
) -> dict[str, object]:
    precision, recall, f1, _ = precision_recall_fscore_support(
        expected,
        predicted,
        labels=labels,
        average="macro",
        zero_division=0,
    )
    weighted_precision, weighted_recall, weighted_f1, _ = (
        precision_recall_fscore_support(
            expected,
            predicted,
            labels=labels,
            average="weighted",
            zero_division=0,
        )
    )
    return {
        "accuracy": float(accuracy_score(expected, predicted)),
        "macro_precision": float(precision),
        "macro_recall": float(recall),
        "macro_f1": float(f1),
        "weighted_precision": float(weighted_precision),
        "weighted_recall": float(weighted_recall),
        "weighted_f1": float(weighted_f1),
        "per_class": classification_report(
            expected,
            predicted,
            labels=labels,
            output_dict=True,
            zero_division=0,
        ),
        "confusion_matrix": confusion_matrix(
            expected, predicted, labels=labels
        ).tolist(),
    }


def write_json(path: Path, value: object) -> None:
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)


def train(args: argparse.Namespace) -> dict[str, object]:
    dataset_dir = args.dataset_dir.resolve()
    if not dataset_dir.is_dir():
        raise ValueError(f"Dataset directory does not exist: {dataset_dir}")

    partitions, dataset_format = discover_records(
        dataset_dir,
        args.annotations,
        args.image_column,
        args.label_column,
        args.split_column,
    )
    skipped_images: list[str] = []
    extracted = {
        name: extract_samples(records, skipped_images)
        for name, records in partitions.items()
    }

    digest_labels: dict[str, set[str]] = {}
    for samples in extracted.values():
        for sample in samples:
            digest_labels.setdefault(sample.digest, set()).add(sample.label)
    conflicting_label_digests = {
        digest for digest, labels in digest_labels.items() if len(labels) > 1
    }
    conflicting_label_images = sum(
        sample.digest in conflicting_label_digests
        for samples in extracted.values()
        for sample in samples
    )
    for partition, samples in extracted.items():
        extracted[partition] = [
            sample
            for sample in samples
            if sample.digest not in conflicting_label_digests
        ]

    cross_partition_duplicates = 0
    if extracted["unassigned"]:
        all_samples, duplicate_count = deduplicate_samples(
            extracted["unassigned"], "unassigned"
        )
        training_samples, remaining_samples = split_samples(all_samples, 0.15)
        validation_samples, testing_samples = split_samples(
            remaining_samples, VALIDATION_FRACTION / 0.15
        )
        duplicate_counts = {"unassigned": duplicate_count}
    else:
        training_samples, duplicate_counts = deduplicate_samples(
            extracted["train"], "training"
        )
        validation_samples, validation_duplicates = deduplicate_samples(
            extracted["validation"], "validation"
        )
        training_digests = {sample.digest for sample in training_samples}
        validation_samples, val_leaks = deduplicate_samples(
            validation_samples,
            "validation",
            blocked_digests=training_digests,
        )
        test_samples, test_duplicates = deduplicate_samples(
            extracted["test"], "test"
        )
        test_blocked = training_digests | {
            sample.digest for sample in validation_samples
        }
        test_samples, test_leaks = deduplicate_samples(
            test_samples,
            "test",
            blocked_digests=test_blocked,
        )
        cross_partition_duplicates = val_leaks + test_leaks
        duplicate_counts = {
            "train": duplicate_counts,
            "validation": validation_duplicates,
            "test": test_duplicates,
        }

        if not test_samples:
            if not validation_samples:
                training_samples, validation_samples = split_samples(
                    training_samples,
                    VALIDATION_FRACTION / (1 - 0.15),
                )
            training_samples, testing_samples = split_samples(
                training_samples, 0.15
            )
        elif not validation_samples:
            training_samples, validation_samples = split_samples(
                training_samples, VALIDATION_FRACTION
            )
            testing_samples = test_samples
        else:
            testing_samples = test_samples

    classes = sorted({sample.label for sample in training_samples})
    if len(classes) < 2:
        raise ValueError("At least two classes must remain in the training split.")
    for partition_name, samples in (
        ("validation", validation_samples),
        ("test", testing_samples),
    ):
        unexpected = sorted({sample.label for sample in samples} - set(classes))
        if unexpected:
            raise ValueError(
                f"{partition_name} contains labels absent from training: {unexpected}"
            )
    if not validation_samples or not testing_samples:
        raise ValueError("Training requires non-empty validation and test splits.")

    train_x, train_y = sample_arrays(training_samples)
    validation_x, validation_y = sample_arrays(validation_samples)
    test_x, test_y = sample_arrays(testing_samples)
    best_model: SGDClassifier | None = None
    best_alpha: float | None = None
    best_validation_metrics: dict[str, object] | None = None
    best_validation_f1 = -1.0
    best_training_f1 = 0.0

    for alpha in (1e-4, 1e-3, 1e-2):
        candidate = make_classifier(alpha)
        candidate.fit(train_x, train_y)
        train_metrics = metric_summary(
            train_y, candidate.predict(train_x), classes
        )
        validation_metrics = metric_summary(
            validation_y, candidate.predict(validation_x), classes
        )
        validation_f1 = float(validation_metrics["macro_f1"])
        logger.info(
            "alpha=%g train macro-F1=%.4f validation macro-F1=%.4f",
            alpha,
            float(train_metrics["macro_f1"]),
            validation_f1,
        )
        if validation_f1 > best_validation_f1:
            best_model = candidate
            best_alpha = alpha
            best_validation_metrics = validation_metrics
            best_validation_f1 = validation_f1
            best_training_f1 = float(train_metrics["macro_f1"])

    if best_model is None or best_alpha is None or best_validation_metrics is None:
        raise RuntimeError("No classifier candidate was successfully trained.")

    final_x = np.vstack((train_x, validation_x))
    final_y = np.concatenate((train_y, validation_y))
    final_model = make_classifier(best_alpha)
    final_model.fit(final_x, final_y)
    test_metrics = metric_summary(test_y, final_model.predict(test_x), classes)
    training_counts = {
        label: int(sum(sample.label == label for sample in training_samples))
        for label in classes
    }
    class_imbalance_ratio = max(training_counts.values()) / min(
        training_counts.values()
    )
    missing_test_classes = sorted(set(classes) - {sample.label for sample in testing_samples})
    if missing_test_classes:
        logger.warning("Test split is missing classes: %s", missing_test_classes)

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / "waste_classifier.joblib"
    temporary_model_path = output_dir / "waste_classifier.joblib.tmp"
    joblib.dump(
        {
            "estimator": final_model,
            "model_version": MODEL_VERSION,
            "classes": classes,
            "feature_size": int(final_x.shape[1]),
            "image_size": [64, 64],
        },
        temporary_model_path,
    )
    temporary_model_path.replace(model_path)

    validation_train_gap = best_training_f1 - best_validation_f1
    evaluation = {
        "model_version": MODEL_VERSION,
        "architecture": "64x64 grayscale HOG + RGB color histogram + SGD logistic classifier",
        "dataset_dir": str(dataset_dir),
        "dataset_format": dataset_format,
        "random_seed": RANDOM_SEED,
        "best_alpha": best_alpha,
        "split_counts": {
            "train": len(training_samples),
            "validation": len(validation_samples),
            "test": len(testing_samples),
        },
        "class_counts": training_counts,
        "class_imbalance_ratio": class_imbalance_ratio,
        "duplicate_files_removed_within_splits": duplicate_counts,
        "conflicting_label_duplicate_hashes": len(conflicting_label_digests),
        "conflicting_label_duplicate_images_excluded": conflicting_label_images,
        "cross_split_duplicate_images_excluded": cross_partition_duplicates,
        "unreadable_images_skipped": len(skipped_images),
        "unreadable_image_paths": skipped_images[:100],
        "test_missing_classes": missing_test_classes,
        "overfit_check": {
            "selected_model_training_macro_f1": best_training_f1,
            "validation_macro_f1": best_validation_f1,
            "training_minus_validation_macro_f1": validation_train_gap,
        },
        "validation": best_validation_metrics,
        "test": test_metrics,
    }
    write_json(
        output_dir / "class_labels.json",
        {
            "classes": classes,
            "category_mapping": {
                label: CLASS_CATEGORY_MAP[label] for label in classes
            },
        },
    )
    write_json(output_dir / "evaluation.json", evaluation)
    write_json(
        output_dir / "confusion_matrix.json",
        {
            "labels": classes,
            "matrix": test_metrics["confusion_matrix"],
        },
    )

    logger.info("Saved trained model to %s", model_path)
    logger.info("Saved evaluation metrics to %s", output_dir / "evaluation.json")
    return {
        "model_path": str(model_path),
        "classes": classes,
        "split_counts": evaluation["split_counts"],
        "test": {
            key: test_metrics[key]
            for key in (
                "accuracy",
                "macro_precision",
                "macro_recall",
                "macro_f1",
                "weighted_precision",
                "weighted_recall",
                "weighted_f1",
            )
        },
        "cross_split_duplicate_images_excluded": cross_partition_duplicates,
        "unreadable_images_skipped": len(skipped_images),
    }


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(
        description="Train EcoSort's CPU-friendly waste-image classifier."
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=project_root / "dataset" / "DATASET",
        help="Folder containing train/test class folders or class folders.",
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        help="Optional CSV annotation file instead of class-wise folders.",
    )
    parser.add_argument("--image-column", default="image")
    parser.add_argument("--label-column", default="label")
    parser.add_argument("--split-column", default="split")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "models",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    result = train(parse_args())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
