"""Tests for errors.py — error hierarchy and validation functions."""

import pytest

from errors import (
    PLATFORM_NAME_RE,
    REPO_COMPONENT_RE,
    VALID_GATES,
    DispatchError,
    GateError,
    MadrugaError,
    PipelineError,
    ValidationError,
    validate_path_safe,
    validate_platform_name,
    validate_repo_component,
)


# ── Error hierarchy ─────────────────────────────────────────────────


class TestErrorHierarchy:
    def test_validation_error_is_madruga_error(self):
        assert issubclass(ValidationError, MadrugaError)

    def test_pipeline_error_is_madruga_error(self):
        assert issubclass(PipelineError, MadrugaError)

    def test_dispatch_error_is_pipeline_error(self):
        assert issubclass(DispatchError, PipelineError)

    def test_gate_error_is_pipeline_error(self):
        assert issubclass(GateError, PipelineError)

    def test_catch_madruga_catches_all(self):
        for cls in (ValidationError, PipelineError, DispatchError, GateError):
            with pytest.raises(MadrugaError):
                raise cls("test")


# ── Constants ────────────────────────────────────────────────────────


class TestConstants:
    def test_valid_gates_contents(self):
        assert VALID_GATES == {"auto", "human", "1-way-door", "auto-escalate"}

    def test_valid_gates_is_frozenset(self):
        assert isinstance(VALID_GATES, frozenset)

    def test_platform_name_re_accepts_valid(self):
        for name in ("foo", "my-platform", "a1", "abc-123-def"):
            assert PLATFORM_NAME_RE.match(name), f"should match: {name}"

    def test_platform_name_re_rejects_invalid(self):
        for name in ("", "1foo", "-foo", "Foo", "foo bar", "foo/bar"):
            assert not PLATFORM_NAME_RE.match(name), f"should not match: {name}"

    def test_repo_component_re_accepts_valid(self):
        for val in ("org", "my.org", "repo_name", "repo-name", "v1.0"):
            assert REPO_COMPONENT_RE.match(val), f"should match: {val}"

    def test_repo_component_re_rejects_invalid(self):
        for val in ("", "a/b", "a b", "org;rm"):
            assert not REPO_COMPONENT_RE.match(val), f"should not match: {val}"


# ── validate_platform_name ──────────────────────────────────────────


class TestValidatePlatformName:
    @pytest.mark.parametrize("name", ["foo", "my-platform", "a1", "abc-123"])
    def test_valid_names_pass(self, name):
        validate_platform_name(name)  # no exception

    @pytest.mark.parametrize(
        "name",
        [
            "",  # empty
            "1foo",  # digit start
            "-foo",  # hyphen start
            "Foo",  # uppercase
            "foo bar",  # space
            "../etc",  # path traversal
            "foo;rm -rf /",  # shell metachar
        ],
    )
    def test_invalid_names_raise(self, name):
        with pytest.raises(ValidationError):
            validate_platform_name(name)


# ── validate_path_safe ──────────────────────────────────────────────


class TestValidatePathSafe:
    @pytest.mark.parametrize("path", ["foo/bar", "a/b/c", "./local", "no-dots"])
    def test_safe_paths_pass(self, path):
        validate_path_safe(path)  # no exception

    @pytest.mark.parametrize(
        "path",
        [
            "../etc/passwd",
            "foo/../../bar",
            "foo/..",
            "../",
        ],
    )
    def test_traversal_paths_raise(self, path):
        with pytest.raises(ValidationError):
            validate_path_safe(path)

    def test_dots_in_filename_ok(self):
        validate_path_safe("foo/bar.txt")  # single dots are fine


# ── validate_repo_component ─────────────────────────────────────────


class TestValidateRepoComponent:
    @pytest.mark.parametrize("val", ["org", "my-org", "repo.name", "under_score"])
    def test_valid_components_pass(self, val):
        validate_repo_component(val)  # no exception

    @pytest.mark.parametrize(
        "val",
        [
            "",  # empty
            "a/b",  # slash
            "a b",  # space
            "org;rm",  # semicolon
            "../up",  # traversal chars
        ],
    )
    def test_invalid_components_raise(self, val):
        with pytest.raises(ValidationError):
            validate_repo_component(val)

    def test_label_appears_in_message(self):
        with pytest.raises(ValidationError, match="repo org"):
            validate_repo_component("", label="repo org")
