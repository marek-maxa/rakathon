"""Exported backup stays offline, inspectable and separate from live decisions."""

import json
from copy import deepcopy

import pytest

from scripts.build_demo import ROOT, build_demo, prepare_cases, structured_baseline


def cases():
    return json.loads((ROOT / "demo/cases.json").read_text(encoding="utf-8"))


def test_six_prepared_cases_use_actual_rules_without_changing_the_inputs():
    source = cases()
    before = deepcopy(source)
    prepared = prepare_cases(source)
    assert source == before
    # Expectations are test-only, never part of the inputs passed to triage.
    expected = {
        "fever": ["red"],
        "colitis": ["yellow", "orange", "yellow"],
        "cardiac": ["yellow", "orange"],
        "bleeding": ["red"],
        "caregiver": ["yellow"],
        "conflict": ["red"],
    }
    assert {
        c["id"]: [s["assessment"]["minimum_color"] for s in c["steps"]]
        for c in prepared
    } == expected
    conflict = prepared[-1]["steps"][0]["assessment"]
    assert any(
        i["code"] == "conflicting_temperature" for i in conflict["review_issues"]
    )
    assert (
        prepared[-2]["steps"][0]["assessment"]["routing"]["contact_code"]
        == "palliative_team_24h"
    )
    trend = prepared[2]["steps"][0]["assessment"]["triage_inputs"]["observations"]
    assert trend["weight_gain_3_days_kg"][0]["value"] == 2.5


def test_titles_and_future_steps_cannot_influence_earlier_decisions():
    source = cases()
    original = prepare_cases(source)
    changed = deepcopy(source)
    for case in changed:
        case.update(id="DO_NOT_USE", title="DO_NOT_USE", source="DO_NOT_USE")
        case["steps"] = case["steps"][:1]
    for before, after in zip(original, prepare_cases(changed), strict=True):
        assert before["steps"][0]["assessment"] == after["steps"][0]["assessment"]
        assert "DO_NOT_USE" not in json.dumps(after["steps"][0]["assessment"])


def test_export_is_self_contained_and_does_not_call_external_services(
    tmp_path, monkeypatch
):
    import urllib.request

    def forbidden(*args, **kwargs):
        pytest.fail("Offline export attempted an external call or patient-store write")

    monkeypatch.setattr("llm_intake.client.Client.from_env", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    monkeypatch.setattr("web.patient_store.append_checkins", forbidden)
    monkeypatch.setattr("notifications.mailer.send_notification", forbidden)
    prepared = build_demo(tmp_path)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    results = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    assert "OFFLINE — předpřipravený průchod" in html
    assert "žádný LLM neběží" in html
    assert "<script" not in html
    assert 'src="http' not in html
    assert 'rel="stylesheet"' not in html
    assert 'method="post"' not in html
    assert results["llm_called"] is False
    assert results["cases"] == prepared
    baseline = results["structured_baseline"]
    assert baseline["mode"] == "structured_only_without_messages"
    assert baseline["checkins"] == sum(baseline["comparisons"].values())
    assert sorted(p.name for p in tmp_path.iterdir()) == ["index.html", "results.json"]
    for case in prepared:
        assert f'id="{case["id"]}"' in html


def test_replay_summary_is_from_the_existing_full_structured_dataset():
    baseline = structured_baseline()
    assert baseline["patients"] == 14
    assert baseline["checkins"] == 171
    assert 0 <= baseline["requires_review"] <= 171


def test_bad_demo_time_is_rejected():
    source = cases()
    source[0]["steps"][0]["at"] = "2026-10-17T10:00:00"
    with pytest.raises(ValueError, match="timezone-aware"):
        prepare_cases(source)
