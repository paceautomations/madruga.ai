"""Path security tests — validate rejection of malicious platform names and repo components."""

import pytest

from errors import ValidationError, validate_path_safe, validate_platform_name, validate_repo_component


class TestPlatformNameSecurity:
    """Platform name must be lowercase kebab-case, starting with a letter."""

    @pytest.mark.parametrize("name", ["myplatform", "my-platform", "a1", "x-1-2"])
    def test_valid_names(self, name: str) -> None:
        validate_platform_name(name)  # should not raise

    @pytest.mark.parametrize(
        "name",
        [
            "../../../etc",
            "../../passwd",
            "; rm -rf /",
            "$(whoami)",
            "`id`",
            "foo|bar",
            "a&b",
            "MyPlatform",
            "UPPER",
            "-leading-hyphen",
            "",
        ],
    )
    def test_rejects_malicious_and_invalid(self, name: str) -> None:
        with pytest.raises(ValidationError):
            validate_platform_name(name)


class TestRepoComponentSecurity:
    """Repo org/name must be alphanumeric + dots/underscores/hyphens."""

    @pytest.mark.parametrize("value", ["my-org", "repo.name", "under_score", "MixedCase123"])
    def test_valid_components(self, value: str) -> None:
        validate_repo_component(value, "org")

    @pytest.mark.parametrize(
        "value",
        [
            "has space",
            "../traversal",
            "; rm -rf",
            "$(cmd)",
            "",
            "a/b",
        ],
    )
    def test_rejects_unsafe_components(self, value: str) -> None:
        with pytest.raises(ValidationError):
            validate_repo_component(value, "org")


class TestPathSafety:
    """Paths must not contain '..' segments."""

    @pytest.mark.parametrize("path", ["platforms/foo/bar", "a/b/c", "simple"])
    def test_valid_paths(self, path: str) -> None:
        validate_path_safe(path)

    @pytest.mark.parametrize("path", ["../../../etc/passwd", "foo/../bar", "a/.."])
    def test_rejects_traversal(self, path: str) -> None:
        with pytest.raises(ValidationError):
            validate_path_safe(path)
