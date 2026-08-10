"""Repository Intelligence — detect language, frameworks, structure."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from core.models.repository import FrameworkInfo, LanguageInfo, RepositoryProfile

logger = logging.getLogger(__name__)

# Heuristic maps
LANGUAGE_MARKERS: dict[str, list[str]] = {
    "python": ["*.py", "requirements.txt", "pyproject.toml", "setup.py", "Pipfile"],
    "javascript": ["package.json", "*.js", "*.mjs"],
    "typescript": ["tsconfig.json", "*.ts", "*.tsx"],
    "java": ["pom.xml", "build.gradle", "*.java"],
    "csharp": ["*.csproj", "*.sln", "*.cs"],
    "go": ["go.mod", "go.sum", "*.go"],
    "ruby": ["Gemfile", "*.rb"],
    "php": ["composer.json", "*.php"],
    "rust": ["Cargo.toml", "*.rs"],
}

TEST_FRAMEWORK_MARKERS: dict[str, list[str]] = {
    "pytest": ["pytest.ini", "conftest.py", "pyproject.toml"],
    "unittest": [],  # detected via imports later
    "playwright": ["playwright.config.*", "package.json"],
    "jest": ["jest.config.*", "package.json"],
    "mocha": ["mocha.opts", "package.json"],
    "cypress": ["cypress.config.*", "cypress.json"],
    "junit": ["pom.xml", "build.gradle"],
    "testng": ["testng.xml"],
    "go_test": ["*_test.go"],
    "dotnet": ["*.csproj"],
}

PACKAGE_MANAGERS: dict[str, str] = {
    "requirements.txt": "pip",
    "pyproject.toml": "pip/poetry/uv",
    "Pipfile": "pipenv",
    "package.json": "npm/yarn/pnpm",
    "pom.xml": "maven",
    "build.gradle": "gradle",
    "build.gradle.kts": "gradle",
    "go.mod": "go",
    "Cargo.toml": "cargo",
    "Gemfile": "bundler",
    "composer.json": "composer",
    "*.csproj": "dotnet",
}

CI_MARKERS: dict[str, list[str]] = {
    "github-actions": [".github/workflows"],
    "gitlab-ci": [".gitlab-ci.yml"],
    "azure-devops": ["azure-pipelines.yml", ".azure-pipelines"],
    "jenkins": ["Jenkinsfile"],
    "circleci": [".circleci"],
}


class RepositoryScanner:
    """Discover repository structure, language, and tooling."""

    def __init__(self, repository_path: str | Path, ignore_patterns: list[str] | None = None) -> None:
        self.root = Path(repository_path).resolve()
        self.ignore_patterns = ignore_patterns or [
            ".git",
            "node_modules",
            "__pycache__",
            ".venv",
            "venv",
            "dist",
            "build",
            ".pytest_cache",
            "coverage",
            ".tox",
            ".mypy_cache",
            ".ruff_cache",
        ]

    def scan(self) -> RepositoryProfile:
        files = self._list_relevant_files()
        language = self._detect_language(files)
        framework = self._detect_framework(files, language.primary)
        source_dirs = self._detect_source_dirs(files, language.primary)
        test_dirs = self._detect_test_dirs(files)
        config_files = self._detect_config_files(files)
        dep_files = self._detect_dependency_files(files)
        ci = self._detect_ci(files)
        test_cmd = self._infer_test_command(framework, language.primary)
        build_cmd = self._infer_build_command(framework, language.primary)
        security_files = self._detect_security_sensitive(files)

        return RepositoryProfile(
            language=language,
            framework=framework,
            architecture_style=self._guess_architecture(files, language.primary),
            source_directories=source_dirs,
            test_directories=test_dirs,
            config_files=config_files,
            dependency_files=dep_files,
            ci_provider=ci,
            test_command=test_cmd,
            build_command=build_cmd,
            has_api_definitions=any(
                "openapi" in f.lower() or "swagger" in f.lower() or f.endswith((".proto", ".graphql"))
                for f in files
            ),
            has_database_code=any(
                any(k in f.lower() for k in ("migration", "models.py", "schema", "repository", "dao"))
                for f in files
            ),
            has_infrastructure=any(
                any(k in f.lower() for k in ("dockerfile", "terraform", "k8s", "helm", "cloudformation"))
                for f in files
            ),
            security_sensitive_files=security_files,
            metadata={"file_count": len(files)},
        )

    def _list_relevant_files(self, max_files: int = 5000) -> list[str]:
        results: list[str] = []
        for p in self.root.rglob("*"):
            if not p.is_file():
                continue
            rel = str(p.relative_to(self.root))
            if any(part in self.ignore_patterns for part in Path(rel).parts):
                continue
            results.append(rel)
            if len(results) >= max_files:
                break
        return results

    def _detect_language(self, files: list[str]) -> LanguageInfo:
        scores: dict[str, int] = {}
        for lang, markers in LANGUAGE_MARKERS.items():
            score = 0
            for m in markers:
                if m.startswith("*."):
                    ext = m[1:]
                    score += sum(1 for f in files if f.endswith(ext))
                else:
                    score += sum(10 for f in files if f == m or f.endswith("/" + m) or Path(f).name == m)
            if score:
                scores[lang] = score
        if not scores:
            return LanguageInfo(primary="unknown", confidence=0.0)
        primary = max(scores, key=scores.get)  # type: ignore[arg-type]
        total = sum(scores.values())
        secondary = [l for l, s in scores.items() if l != primary and s > 0]
        return LanguageInfo(
            primary=primary,
            secondary=secondary[:3],
            confidence=min(1.0, scores[primary] / max(total, 1)),
        )

    def _detect_framework(self, files: list[str], language: str) -> FrameworkInfo:
        test_fw = None
        web_fw = None
        build = None
        pkg = None

        names = {Path(f).name for f in files}
        lower_files = [f.lower() for f in files]

        # Package manager
        for marker, pm in PACKAGE_MANAGERS.items():
            if marker.startswith("*."):
                if any(f.endswith(marker[1:]) for f in files):
                    pkg = pm
                    break
            elif marker in names:
                pkg = pm
                break

        # Test framework heuristics
        if language == "python":
            if "pytest.ini" in names or "conftest.py" in names or any("pytest" in f for f in lower_files):
                test_fw = "pytest"
            if any("playwright" in f for f in lower_files):
                test_fw = (test_fw or "") + "+playwright" if test_fw else "playwright"
            if "manage.py" in names:
                web_fw = "django"
            if any("fastapi" in f for f in lower_files) or any("from fastapi" in f for f in []):
                web_fw = web_fw or "fastapi"
        elif language in ("javascript", "typescript"):
            if "package.json" in names:
                # Lightweight read
                pkg_path = self.root / "package.json"
                try:
                    import json
                    data = json.loads(pkg_path.read_text(encoding="utf-8"))
                    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                    if "playwright" in deps or "@playwright/test" in deps:
                        test_fw = "playwright"
                    elif "jest" in deps:
                        test_fw = "jest"
                    elif "cypress" in deps:
                        test_fw = "cypress"
                    elif "mocha" in deps:
                        test_fw = "mocha"
                    if "react" in deps:
                        web_fw = "react"
                    elif "vue" in deps:
                        web_fw = "vue"
                    elif "express" in deps:
                        web_fw = "express"
                    elif "next" in deps:
                        web_fw = "next"
                except Exception:
                    pass
        elif language == "java":
            if "pom.xml" in names:
                build = "maven"
                test_fw = "junit"
            elif any("build.gradle" in f for f in files):
                build = "gradle"
                test_fw = "junit"
        elif language == "go":
            test_fw = "go_test"
            build = "go"
        elif language == "csharp":
            test_fw = "dotnet"
            build = "dotnet"

        return FrameworkInfo(
            name=web_fw or language,
            test_framework=test_fw,
            web_framework=web_fw,
            build_system=build,
            package_manager=pkg,
        )

    def _detect_source_dirs(self, files: list[str], language: str) -> list[str]:
        candidates = ["src", "lib", "app", "source", "pkg", language]
        found = []
        for c in candidates:
            if any(f.startswith(c + "/") or f == c for f in files):
                found.append(c + "/")
        # Python packages often at root
        if language == "python" and not found:
            for f in files:
                if f.endswith(".py") and "/" not in f:
                    found.append(".")
                    break
        return found[:5] or ["."]

    def _detect_test_dirs(self, files: list[str]) -> list[str]:
        candidates = ["tests", "test", "spec", "__tests__", "e2e", "integration"]
        found = []
        for c in candidates:
            if any(f.startswith(c + "/") or f.startswith(c + "\\") for f in files):
                found.append(c + "/")
        return found[:5]

    def _detect_config_files(self, files: list[str]) -> list[str]:
        config_names = {
            "pyproject.toml",
            "setup.cfg",
            "setup.py",
            "package.json",
            "tsconfig.json",
            "pom.xml",
            "build.gradle",
            "go.mod",
            "Dockerfile",
            "docker-compose.yml",
            ".env.example",
            "qgate.yaml",
        }
        return [f for f in files if Path(f).name in config_names][:20]

    def _detect_dependency_files(self, files: list[str]) -> list[str]:
        dep_names = {
            "requirements.txt",
            "pyproject.toml",
            "Pipfile",
            "package.json",
            "package-lock.json",
            "yarn.lock",
            "pom.xml",
            "build.gradle",
            "go.mod",
            "Cargo.toml",
            "Gemfile",
            "composer.json",
        }
        return [f for f in files if Path(f).name in dep_names]

    def _detect_ci(self, files: list[str]) -> str | None:
        for provider, markers in CI_MARKERS.items():
            for m in markers:
                if any(f.startswith(m) or f == m for f in files):
                    return provider
        return None

    def _infer_test_command(self, framework: FrameworkInfo, language: str) -> str | None:
        tf = framework.test_framework or ""
        if "pytest" in tf:
            return "pytest"
        if "playwright" in tf:
            return "npx playwright test"
        if tf == "jest":
            return "npm test"
        if tf == "junit" and framework.build_system == "maven":
            return "mvn test"
        if tf == "junit" and framework.build_system == "gradle":
            return "gradle test"
        if tf == "go_test":
            return "go test ./..."
        if tf == "dotnet":
            return "dotnet test"
        if language == "python":
            return "pytest"
        return None

    def _infer_build_command(self, framework: FrameworkInfo, language: str) -> str | None:
        if framework.build_system == "maven":
            return "mvn package"
        if framework.build_system == "gradle":
            return "gradle build"
        if framework.build_system == "go":
            return "go build ./..."
        if framework.build_system == "dotnet":
            return "dotnet build"
        return None

    def _guess_architecture(self, files: list[str], language: str) -> str | None:
        lower = [f.lower() for f in files]
        if any("page" in f and "object" in f for f in lower) or any("pages/" in f for f in lower):
            return "page-object"
        if any("controllers/" in f or "services/" in f or "repositories/" in f for f in lower):
            return "layered"
        if any("apps/" in f and "packages/" in f for f in lower):
            return "monorepo"
        return None

    def _detect_security_sensitive(self, files: list[str]) -> list[str]:
        sensitive = []
        keywords = ("secret", "credential", "password", "token", "key", ".env", "auth", "cert")
        for f in files:
            fl = f.lower()
            if any(k in fl for k in keywords):
                sensitive.append(f)
        return sensitive[:30]
