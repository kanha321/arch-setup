import pytest

from profile_switcher.lock import LockHeld, switch_lock


def test_second_acquire_fails_fast(tmp_path):
    p = tmp_path / "run" / "switch.lock"
    with switch_lock(p), pytest.raises(LockHeld, match="in progress"), switch_lock(p):
        pass


def test_lock_released_after_use(tmp_path):
    p = tmp_path / "switch.lock"
    with switch_lock(p):
        pass
    with switch_lock(p):
        pass
