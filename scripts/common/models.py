from dataclasses import dataclass
from typing import Optional


@dataclass
class ManifestEntry:
    service_id: str
    display_name: str
    source_path: str
    local_path: str
    source_format: str          # "yaml" or "json"
    openapi_version: str
    info_title: str
    info_version: str
    spec_hash: str
    fetched_at: str
    source_commit: Optional[str] = None
    published_url: Optional[str] = None


@dataclass
class RegistryEntry:
    service_id: str
    source_path: str
    last_processed_hash: str
    last_processed_at: str
    output_file: str
    output_hash: str
    status: str                 # "success", "failed", "skipped"
    notes: str = ""


@dataclass
class GenerationRequest:
    service_id: str
    display_name: str
    source_path: str
    spec_hash: str
    openapi_version: str
    info_title: str
    info_version: str
    ai_input: dict
    chunk_index: Optional[int] = None
    total_chunks: Optional[int] = None


@dataclass
class GenerationResult:
    service_id: str
    success: bool
    output_path: Optional[str] = None
    output_hash: Optional[str] = None
    error: Optional[str] = None
