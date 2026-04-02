"""Update a processing registry dict in-place with the result for one spec."""
from datetime import datetime, timezone


def update_registry(
    registry: dict,
    service_id: str,
    source_path: str,
    spec_hash: str,
    output_file: str,
    output_hash: str,
    status: str,
    notes: str = "",
):
    """Mutate *registry* to record the processing result for *service_id*."""
    if "specs" not in registry:
        registry["specs"] = {}

    registry["specs"][service_id] = {
        "service_id": service_id,
        "source_path": source_path,
        "last_processed_hash": spec_hash,
        "last_processed_at": datetime.now(timezone.utc).isoformat(),
        "output_file": output_file,
        "output_hash": output_hash,
        "status": status,
        "notes": notes,
        # Placeholder fields for future Confluence sync
        "confluence_page_id": None,
        "confluence_synced_at": None,
    }
