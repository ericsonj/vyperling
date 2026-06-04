"""Tests for vyperling.errors — ForgeError hierarchy."""

import pytest

from vyperling.errors import (
    ForgeCompileError,
    ForgeConfigError,
    ForgeError,
    ForgeMockgenError,
    ForgeToolchainError,
)

SUBCLASSES = [ForgeConfigError, ForgeToolchainError, ForgeCompileError, ForgeMockgenError]


class TestInheritance:
    def test_forge_error_is_exception(self):
        assert issubclass(ForgeError, Exception)

    @pytest.mark.parametrize("cls", SUBCLASSES)
    def test_subclass_of_forge_error(self, cls):
        assert issubclass(cls, ForgeError)

    @pytest.mark.parametrize("cls", SUBCLASSES)
    def test_subclass_of_exception(self, cls):
        assert issubclass(cls, Exception)

    @pytest.mark.parametrize("a", SUBCLASSES)
    @pytest.mark.parametrize("b", SUBCLASSES)
    def test_subclasses_not_related(self, a, b):
        if a is not b:
            assert not issubclass(a, b)


class TestRaiseAndCatch:
    @pytest.mark.parametrize("cls", [ForgeError] + SUBCLASSES)
    def test_caught_as_forge_error(self, cls):
        with pytest.raises(ForgeError):
            raise cls("test message")

    @pytest.mark.parametrize("cls", [ForgeError] + SUBCLASSES)
    def test_message_preserved(self, cls):
        msg = "something went wrong"
        with pytest.raises(cls) as exc_info:
            raise cls(msg)
        assert str(exc_info.value) == msg
