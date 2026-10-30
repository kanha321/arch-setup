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


class FakeClock:
    def __init__(self):
        self.t = 0.0
        self.sleeps: list[float] = []

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds
        self.sleeps.append(seconds)


@pytest.fixture
def clock():
    return FakeClock()
