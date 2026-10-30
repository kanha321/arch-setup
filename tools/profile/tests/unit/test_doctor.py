from profile_switcher.doctor import find_overlaps


def test_no_overlap():
    files = {"common": {".config/fish/config.fish"}, "dms": {".config/dms/a"}}
    assert find_overlaps(files) == {}


def test_overlap_reports_path_and_owners():
    files = {
        "common": {".config/hypr/binds.lua", ".gitconfig"},
        "caelestia": {".config/hypr/binds.lua"},
        "dms": {".config/dms/a"},
    }
    assert find_overlaps(files) == {".config/hypr/binds.lua": ["caelestia", "common"]}


def test_three_way_overlap_lists_all_owners_sorted():
    files = {"c": {"x"}, "b": {"x"}, "a": {"x"}}
    assert find_overlaps(files) == {"x": ["a", "b", "c"]}


def test_empty_input():
    assert find_overlaps({}) == {}
