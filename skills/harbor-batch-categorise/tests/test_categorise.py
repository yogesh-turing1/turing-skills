#!/usr/bin/env python3
"""The Company Bench label, exactly as COMPANY-BENCH-CATEGORIES.md defines it."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
from categorise import connector_count, harness_of, label  # noqa: E402


def test_harness_from_the_image_name():
    assert harness_of("kuzphi/connectors-harness-aster@sha256:abc", []) == "Aster"
    assert harness_of("kuzphi/company-bench-private:zeta-newdbs2-20260918", []) == "Zeta"


def test_harness_falls_back_to_the_connectors_when_no_image():
    assert harness_of("", ["zeta3-sql-gym", "jira-gym"]) == "Zeta"
    assert harness_of("", ["github"]) == "Aster"
    assert harness_of("", ["notion-gym"]) == "Aster"
    assert harness_of("", ["outlook-gym"]) == "Aster"
    assert harness_of("", ["email-calendar-gym"]) == "Aster"


def test_google_workspace_is_aster_under_any_of_its_names():
    # the doc names it "Google Workspace"; the packages call it gws-gym
    assert harness_of("", ["gws-gym"]) == "Aster"
    assert harness_of("", ["google-workspace-gym"]) == "Aster"


def test_harness_unresolved_when_nothing_says():
    # google drive and slack exist on both harnesses, so neither settles it
    assert harness_of("", ["google-drive-gym"]) == "Company Bench"
    assert harness_of("", ["slack-gym"]) == "Company Bench"
    assert harness_of("", []) == "Company Bench"


def test_only_real_tools_count():
    assert connector_count(["harbor"]) == 0
    assert connector_count(["harbor", "read-only", "quality-review"]) == 0
    assert connector_count(["jira-gym", "harbor"]) == 1


def test_the_same_tool_written_two_ways_counts_once():
    assert connector_count(["slack", "slack-gym"]) == 1
    assert connector_count(["github", "github-gym"]) == 1


def test_bare_names_that_count_without_a_gym_suffix():
    assert connector_count(["slack", "linear", "github", "notion"]) == 4


def test_label_single_and_multi():
    assert label("", ["notion-gym"]) == "Aster · Single connector"
    assert label("", ["zeta3-sql-gym", "jira-gym", "slack-gym"]) == "Zeta · Multi-connector"


def test_label_when_no_tools_are_listed_at_all():
    assert label("", ["harbor"]) == "Company Bench · connectors not read"
    assert label("", []) == "Company Bench · connectors not read"


def test_an_image_wins_over_the_connectors():
    # a zeta image with a single aster-ish tool is still Zeta
    assert label("reg/zeta-v3@sha256:x", ["github"]) == "Zeta · Single connector"
