import json
import os
from collections.abc import Mapping

from app.ml.inference import CLASS_CATEGORY_MAP

ROUTING_ENVIRONMENT_VARIABLE = "ECOSORT_COMPLAINT_ROUTING_JSON"
DEFAULT_FALLBACK_DEPARTMENT = "General municipal sanitation (manual review)"


def load_complaint_routing() -> dict[str, object]:
    raw_configuration = os.getenv(ROUTING_ENVIRONMENT_VARIABLE)
    if not raw_configuration:
        return {
            "locations": {},
            "fallback_department": DEFAULT_FALLBACK_DEPARTMENT,
        }

    try:
        configuration = json.loads(raw_configuration)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{ROUTING_ENVIRONMENT_VARIABLE} must contain valid JSON."
        ) from exc
    if not isinstance(configuration, dict):
        raise ValueError("Complaint-routing configuration must be a JSON object.")
    unknown_options = set(configuration) - {"locations", "fallback_department"}
    if unknown_options:
        raise ValueError(
            "Unsupported complaint-routing option(s): "
            + ", ".join(sorted(unknown_options))
        )

    fallback = configuration.get("fallback_department", DEFAULT_FALLBACK_DEPARTMENT)
    locations = configuration.get("locations", {})
    if not isinstance(fallback, str) or not fallback.strip():
        raise ValueError("fallback_department must be a non-empty string.")
    if not isinstance(locations, dict):
        raise ValueError("locations must be an object keyed by known location.")

    normalized_locations: dict[str, dict[str, str]] = {}
    for location, category_routes in locations.items():
        if not isinstance(location, str) or not location.strip():
            raise ValueError("Configured location keys must be non-empty strings.")
        if not isinstance(category_routes, dict):
            raise ValueError(f"Routes for {location!r} must be an object.")
        normalized_routes: dict[str, str] = {}
        for category, department in category_routes.items():
            if category not in CLASS_CATEGORY_MAP.values():
                raise ValueError(
                    f"Unsupported waste category {category!r} in routing rules."
                )
            if not isinstance(department, str) or not department.strip():
                raise ValueError(
                    f"Department for {location!r}/{category!r} must be non-empty."
                )
            normalized_routes[category] = department.strip()
        normalized_location = location.strip().casefold()
        if normalized_location in normalized_locations:
            raise ValueError(
                f"Duplicate location rule after case normalization: {location!r}."
            )
        normalized_locations[normalized_location] = normalized_routes

    return {
        "locations": normalized_locations,
        "fallback_department": fallback.strip(),
    }


def route_complaint(
    routing: Mapping[str, object], location: str, waste_category: str
) -> str:
    locations = routing["locations"]
    fallback = routing["fallback_department"]
    if not isinstance(locations, Mapping) or not isinstance(fallback, str):
        raise ValueError("Complaint-routing configuration was not initialized.")
    location_routes = locations.get(location.strip().casefold())
    if isinstance(location_routes, Mapping):
        department = location_routes.get(waste_category)
        if isinstance(department, str) and department:
            return department
    return fallback
