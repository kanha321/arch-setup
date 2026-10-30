import pytest

from profile_switcher.runner import Result


class FakeRunner:
    def __init__(self):
        self.calls: list[list[str]] = []
        self.responses: dict[tuple[str, ...], Result] = {}

    def set(self, cmd, result):
        self.responses[tuple(cmd)] = result

    def run(self, cmd, timeout=10):
        self.calls.append(list(cmd))
        return self.responses.get(tuple(cmd), Result(0))


@pytest.fixture
def runner():
    return FakeRunner()
