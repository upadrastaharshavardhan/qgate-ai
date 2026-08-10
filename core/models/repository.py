"""Repository discovery models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LanguageInfo(BaseModel):
    primary: str = "unknown"
    secondary: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class FrameworkInfo(BaseModel):
    name: str = "unknown"
    test_framework: str | None = None
    web_framework: str | None = None
    build_system: str | None = None
    package_manager: str | None = None


class RepositoryProfile(BaseModel):
    """Result of Repository Intelligence Agent."""

    language: LanguageInfo = Field(default_factory=LanguageInfo)
    framework: FrameworkInfo = Field(default_factory=FrameworkInfo)
    architecture_style: str | None = None  # e.g. page-object, layered, microservices
    source_directories: list[str] = Field(default_factory=list)
    test_directories: list[str] = Field(default_factory=list)
    config_files: list[str] = Field(default_factory=list)
    dependency_files: list[str] = Field(default_factory=list)
    ci_provider: str | None = None
    test_command: str | None = None
    build_command: str | None = None
    has_api_definitions: bool = False
    has_database_code: bool = False
    has_infrastructure: bool = False
    security_sensitive_files: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
