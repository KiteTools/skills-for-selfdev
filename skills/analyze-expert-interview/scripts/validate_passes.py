#!/usr/bin/env python3
"""Validate isolated analysis passes and their optional synthesis bundle."""

import argparse
import json
import re
import sys
from pathlib import Path


EVIDENCE = {"quote", "start_ms", "segment_id"}
META = {"title", "source_url", "duration_ms", "source_format"}
UNCERTAINTY = {"id", "target_ids", "reason", "impact"}
CANDIDATE = {"id", "title", "body", "source_ids", "evidence"}
STRUCTURE_KEYS = {"schema_version", "pass", "input", "structural_chaos", "topics", "observations", "recommendation_candidates", "uncertainties"}
LOGIC_KEYS = {"schema_version", "pass", "input", "logical_soundness", "observations", "theses", "defects", "strong_moments", "recommendation_candidates", "uncertainties"}
_PUNCTUATION_TRANSLATION = str.maketrans({"‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'", "“": '"', "”": '"', "„": '"', "‟": '"', "″": '"', "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-", "−": "-", "…": "...", "\u00a0": " "})


def _fail(message):
    raise ValueError(message)


def _obj(value, path):
    if not isinstance(value, dict): _fail(f"{path} must be an object")
    return value


def _list(value, path, nonempty=False):
    if not isinstance(value, list) or (nonempty and not value): _fail(f"{path} must be {'non-empty ' if nonempty else ''}list")
    return value


def _string(value, path):
    if not isinstance(value, str) or not value.strip(): _fail(f"{path} must be non-empty string")
    return value


def _integer(value, path):
    if isinstance(value, bool) or not isinstance(value, int): _fail(f"{path} must be integer")
    return value


def _exact_keys(value, expected, path):
    actual = set(_obj(value, path))
    missing, extra = expected - actual, actual - expected
    if missing: _fail(f"{path} missing required: {', '.join(sorted(missing))}")
    if extra: _fail(f"{path} additional properties: {', '.join(sorted(extra))}")


def _words(text):
    return re.findall(r"\w+", " ".join(text.casefold().split()), flags=re.UNICODE)


def _segments(normalized):
    result = []
    for segment in _list(_obj(normalized, "normalized").get("segments"), "normalized.segments"):
        result.append(_obj(segment, "normalized.segment"))
    return result


def _normalise_text(value):
    return " ".join(str(value).translate(_PUNCTUATION_TRANSLATION).casefold().split())


def _evidence_occurrences(quote, segments):
    needle = _normalise_text(quote)
    runs, current = [], []
    for segment in segments:
        contiguous = current and current[-1].get("end_ms") is not None and current[-1].get("end_ms") == segment.get("start_ms")
        if segment.get("speaker") == "GUEST" and (not current or contiguous):
            current.append(segment)
        else:
            if current: runs.append(current)
            current = [segment] if segment.get("speaker") == "GUEST" else []
    if current: runs.append(current)
    matches = []
    for run in runs:
        speech, starts = "", []
        for segment in run:
            if speech: speech += " "
            starts.append(len(speech))
            speech += _normalise_text(segment.get("text", ""))
        cursor = 0
        while True:
            found = speech.find(needle, cursor)
            if found < 0: break
            index = max(index for index, offset in enumerate(starts) if offset <= found)
            matches.append(run[index])
            cursor = found + 1
    return matches


def _validate_evidence(item, segments, path):
    _exact_keys(item, EVIDENCE, path)
    quote, start, segment_id = _string(item["quote"], f"{path}.quote"), _integer(item["start_ms"], f"{path}.start_ms"), _string(item["segment_id"], f"{path}.segment_id")
    if start < 0 or len(_words(quote)) < 4: _fail(f"{path} has invalid evidence")
    segment = next((value for value in segments if value.get("id") == segment_id), None)
    if not segment or segment.get("speaker") != "GUEST": _fail(f"{path}.segment_id must resolve to GUEST")
    end = segment.get("end_ms")
    if not (segment.get("start_ms") <= start and (end is None or start < end)): _fail(f"{path}.start_ms outside segment")
    if not any(match.get("id") == segment_id for match in _evidence_occurrences(quote, segments)):
        _fail(f"{path}.quote must start in the stated starting GUEST segment")


def _evidence_fingerprint(value):
    return _normalise_text(value["quote"]), value["start_ms"], value["segment_id"]


def _observation_fingerprint(value):
    return (
        value["kind"],
        tuple(sorted(value.get("topic_ids", []))),
        _normalise_text(value["analysis"]),
        tuple(sorted(_evidence_fingerprint(evidence) for evidence in value["evidence"])),
    )


def _strong_moment_fingerprint(value):
    return (
        _normalise_text(value["title"]),
        _normalise_text(value["analysis"]),
        tuple(sorted(_evidence_fingerprint(evidence) for evidence in value["evidence"])),
    )


def _validate_structure_score_evidence(score, observations):
    if score["score"] <= 4:
        return
    score_evidences = {_evidence_fingerprint(evidence) for evidence in score["evidence"]}
    observation_fingerprints = {}
    for observation in observations:
        fingerprint = _observation_fingerprint(observation)
        for evidence in observation["evidence"]:
            observation_fingerprints.setdefault(_evidence_fingerprint(evidence), set()).add(fingerprint)
    unmatched = score_evidences - set(observation_fingerprints)
    if unmatched:
        _fail("structure score evidence must map to observation evidence")
    assigned = {}

    def assign(evidence, visited):
        for fingerprint in sorted(observation_fingerprints[evidence], key=repr):
            if fingerprint in visited:
                continue
            visited.add(fingerprint)
            previous = assigned.get(fingerprint)
            if previous is None or assign(previous, visited):
                assigned[fingerprint] = evidence
                return True
        return False

    distinct_observations = sum(assign(evidence, set()) for evidence in sorted(score_evidences, key=repr))
    required = 3 if score["score"] >= 7 else 2
    if distinct_observations < required:
        _fail("structure score evidence threshold unmet")


def _validate_input(value, metadata, path):
    _exact_keys(value, {"normalized_metadata", "guest_label"}, path)
    if value["normalized_metadata"] != metadata: _fail(f"{path}.normalized_metadata must equal normalized metadata")
    if value["guest_label"] != "GUEST": _fail(f"{path}.guest_label must be GUEST")


def _validate_uncertainties(items, ids, path):
    for index, item in enumerate(_list(items, path)):
        item_path = f"{path}[{index}]"; _exact_keys(item, UNCERTAINTY, item_path)
        uid = _string(item["id"], f"{item_path}.id")
        if uid in ids: _fail(f"{path} duplicate id")
        ids.add(uid)
        if not set(_list(item["target_ids"], f"{item_path}.target_ids")).issubset(ids): _fail(f"{item_path}.target_ids unresolved")
        _string(item["reason"], f"{item_path}.reason")
        if item["impact"] not in {"low", "medium", "high"}: _fail(f"{item_path}.impact invalid")


def _validate_candidates(items, allowed_source_ids, ids, segments, path):
    candidates = {}
    for index, item in enumerate(_list(items, path, True)):
        item_path = f"{path}[{index}]"; _exact_keys(item, CANDIDATE, item_path)
        cid = _string(item["id"], f"{item_path}.id")
        if cid in ids: _fail(f"{path} duplicate id")
        ids.add(cid); _string(item["title"], f"{item_path}.title"); _string(item["body"], f"{item_path}.body")
        item_source_ids = _list(item["source_ids"], f"{item_path}.source_ids", True)
        if not set(item_source_ids).issubset(allowed_source_ids): _fail(f"{item_path}.source_ids unresolved")
        for evidence_index, evidence in enumerate(_list(item["evidence"], f"{item_path}.evidence", True)):
            _validate_evidence(evidence, segments, f"{item_path}.evidence[{evidence_index}]")
        candidates[cid] = item
    if len(candidates) < 3: _fail(f"{path} must contain at least 3 candidates")
    return candidates


def _validate_structure(doc, metadata, segments):
    _exact_keys(doc, STRUCTURE_KEYS, "structure")
    if doc.get("schema_version") != "1.0" or doc.get("pass") != "structure": _fail("structure schema_version or pass invalid")
    _validate_input(doc["input"], metadata, "structure.input")
    score = _obj(doc["structural_chaos"], "structure.structural_chaos")
    _exact_keys(score, {"score", "rationale", "evidence"}, "structure.structural_chaos")
    if isinstance(score["score"], bool) or not isinstance(score["score"], (int, float)) or not 0 <= score["score"] <= 10: _fail("structure score invalid")
    _string(score["rationale"], "structure.structural_chaos.rationale")
    for i, evidence in enumerate(_list(score["evidence"], "structure.structural_chaos.evidence", True)): _validate_evidence(evidence, segments, f"structure.structural_chaos.evidence[{i}]")
    topics, ids, topic_ids = _list(doc["topics"], "structure.topics", True), set(), set()
    duration = metadata.get("duration_ms")
    for i, topic in enumerate(topics):
        path = f"structure.topics[{i}]"; _exact_keys(topic, {"id", "label", "color", "spans"}, path); tid = _string(topic["id"], f"{path}.id")
        if tid in ids: _fail("structure topics duplicate id")
        ids.add(tid); topic_ids.add(tid); _string(topic["label"], f"{path}.label")
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", topic["color"]): _fail(f"{path}.color invalid")
        for j, span in enumerate(_list(topic["spans"], f"{path}.spans", True)):
            span_path = f"{path}.spans[{j}]"; _exact_keys(span, {"start_ms", "end_ms", "weight", "note"}, span_path)
            start, end = _integer(span["start_ms"], f"{span_path}.start_ms"), _integer(span["end_ms"], f"{span_path}.end_ms")
            if start < 0 or start >= end or (duration is not None and end > duration): _fail(f"{span_path} bounds invalid")
            if span["weight"] not in {"dominant", "touched"}: _fail(f"{span_path}.weight invalid")
            _string(span["note"], f"{span_path}.note")
    observations, observation_ids = [], set()
    for i, item in enumerate(_list(doc["observations"], "structure.observations")):
        path = f"structure.observations[{i}]"; _exact_keys(item, {"id", "kind", "topic_ids", "analysis", "evidence"}, path); oid = _string(item["id"], f"{path}.id")
        if oid in ids: _fail("structure observations duplicate id")
        ids.add(oid); observation_ids.add(oid); observations.append(item)
        if item["kind"] not in {"transition", "return", "digression", "nested_digression", "loop", "abandoned_thread", "answer_directness"}: _fail(f"{path}.kind invalid")
        if not set(_list(item["topic_ids"], f"{path}.topic_ids", True)).issubset(topic_ids): _fail(f"{path}.topic_ids unresolved")
        _string(item["analysis"], f"{path}.analysis")
        for j, evidence in enumerate(_list(item["evidence"], f"{path}.evidence", True)): _validate_evidence(evidence, segments, f"{path}.evidence[{j}]")
    _validate_structure_score_evidence(score, observations)
    candidates = _validate_candidates(doc["recommendation_candidates"], observation_ids, ids, segments, "structure.recommendation_candidates")
    _validate_uncertainties(doc["uncertainties"], ids, "structure.uncertainties")
    return {"score": score["score"], "topics": topics, "observations": observations, "candidates": candidates}


def _validate_logic(doc, metadata, segments):
    _exact_keys(doc, LOGIC_KEYS, "logic")
    if doc.get("schema_version") != "1.0" or doc.get("pass") != "logic": _fail("logic schema_version or pass invalid")
    _validate_input(doc["input"], metadata, "logic.input")
    score = _obj(doc["logical_soundness"], "logic.logical_soundness"); _exact_keys(score, {"score", "rationale", "evidence"}, "logic.logical_soundness")
    if isinstance(score["score"], bool) or not isinstance(score["score"], (int, float)) or not 0 <= score["score"] <= 10: _fail("logic score invalid")
    _string(score["rationale"], "logic.logical_soundness.rationale")
    for i, evidence in enumerate(_list(score["evidence"], "logic.logical_soundness.evidence", True)): _validate_evidence(evidence, segments, f"logic.logical_soundness.evidence[{i}]")
    observations, ids = [], set()
    for i, item in enumerate(_list(doc["observations"], "logic.observations")):
        path = f"logic.observations[{i}]"; _exact_keys(item, {"id", "kind", "analysis", "evidence"}, path); oid = _string(item["id"], f"{path}.id")
        if oid in ids: _fail("logic observations duplicate id")
        ids.add(oid); observations.append(item)
        if item["kind"] not in {"claim_chain", "reasoning_gap", "qualification", "term_definition", "counterexample", "conclusion"}: _fail(f"{path}.kind invalid")
        _string(item["analysis"], f"{path}.analysis")
        for j, evidence in enumerate(_list(item["evidence"], f"{path}.evidence", True)): _validate_evidence(evidence, segments, f"{path}.evidence[{j}]")
    def checked(collection, keys, extra):
        result = []; local_ids = set()
        for i, item in enumerate(_list(doc[collection], f"logic.{collection}")):
            path = f"logic.{collection}[{i}]"; _exact_keys(item, keys, path); iid = _string(item["id"], f"{path}.id")
            if iid in ids or iid in local_ids: _fail(f"logic duplicate id {iid}")
            local_ids.add(iid); result.append(item)
            if not set(_list(item["observation_ids"], f"{path}.observation_ids", True)).issubset(ids): _fail(f"{path}.observation_ids unresolved")
            for j, evidence in enumerate(_list(item["evidence"], f"{path}.evidence", True)): _validate_evidence(evidence, segments, f"{path}.evidence[{j}]")
            extra(item, path)
        ids.update(local_ids); return result
    theses = checked("theses", {"id", "claim", "status", "premises", "evidence", "conclusion", "observation_ids"}, lambda x,p: (_string(x["claim"], p+".claim"), _string(x["conclusion"], p+".conclusion"), _list(x["premises"], p+".premises", x["status"] == "supported"), None if x["status"] in {"supported", "partially_supported", "unsupported"} else _fail(p+".status invalid")))
    defects = checked("defects", {"id", "category", "analysis", "evidence", "observation_ids"}, lambda x,p: (_string(x["analysis"], p+".analysis"), None if x["category"] in {"unsupported_claim", "contradiction", "non_sequitur", "undefined_term", "overgeneralisation", "missing_qualification", "abandoned_reasoning"} else _fail(p+".category invalid")))
    strong = checked("strong_moments", {"id", "title", "analysis", "evidence", "observation_ids"}, lambda x,p: (_string(x["title"], p+".title"), _string(x["analysis"], p+".analysis")))
    if score["score"] < 7 and len({x["category"] for x in defects}) != len(defects): _fail("logic score threshold needs distinct defect categories")
    if score["score"] > 7 and len({_strong_moment_fingerprint(item) for item in strong}) < 2: _fail("logic score threshold needs two distinct strong moments")
    allowed_candidate_sources = set(ids)
    candidates = _validate_candidates(doc["recommendation_candidates"], allowed_candidate_sources, ids, segments, "logic.recommendation_candidates")
    _validate_uncertainties(doc["uncertainties"], ids, "logic.uncertainties")
    return {"score": score["score"], "observations": observations, "theses": theses, "defects": defects, "strong": strong, "candidates": candidates}


def _report_evidence(value):
    return value.get("quote"), value.get("start_ms")


def _validate_report(report, struct, logic):
    report = _obj(report, "report")
    if report.get("scores", {}).get("structural_chaos") != struct["score"] or report.get("scores", {}).get("logical_soundness") != logic["score"]: _fail("report scores must exactly map pass scores")
    if report.get("topics") != struct["topics"]: _fail("report topics must exactly map structure topics")
    events = _list(_obj(report.get("structure"), "report.structure").get("events"), "report.structure.events")
    if len(events) != len(struct["observations"]): _fail("report structure event cardinality mismatch")
    for output, source in zip(events, struct["observations"]):
        if output.get("kind") != source["kind"] or output.get("analysis") != source["analysis"] or (output.get("quote"), output.get("start_ms")) not in {_report_evidence(evidence) for evidence in source["evidence"]}:
            _fail("report structure event mapping mismatch")
    logic_report = _obj(report.get("logic"), "report.logic")
    for name, source, key in (("theses", logic["theses"], "claim"), ("strong_moments", logic["strong"], "title")):
        outputs = _list(logic_report.get(name), f"report.logic.{name}")
        if len(outputs) != len(source): _fail(f"report {name} cardinality mismatch")
        for output, item in zip(outputs, source):
            output_label = key if name == "strong_moments" else "thesis"
            if _report_evidence(output) not in {_report_evidence(evidence) for evidence in item["evidence"]} or output.get(output_label) != item[key]: _fail(f"report {name} mapping mismatch")
            if name == "theses" and (output.get("status") != item["status"] or output.get("support") != item["conclusion"]): _fail("report theses mapping mismatch")
            if name == "strong_moments" and output.get("analysis") != item["analysis"]: _fail("report strong_moments mapping mismatch")
    outputs = _list(logic_report.get("defects"), "report.logic.defects")
    if len(outputs) != len(logic["defects"]): _fail("report defects cardinality mismatch")
    for output, item in zip(outputs, logic["defects"]):
        ex = output.get("example", {})
        if output.get("category") != item["category"] or output.get("count") != 1 or _report_evidence(ex) not in {_report_evidence(evidence) for evidence in item["evidence"]} or ex.get("analysis") != item["analysis"]: _fail("report defects mapping mismatch")
    selected = _list(report.get("recommendations"), "report.recommendations")
    if len(selected) != 5: _fail("report requires exactly 5 recommendations")
    seen = set()
    pools = {"structure": struct["candidates"], "logic": logic["candidates"]}
    for i, rec in enumerate(selected):
        path = f"report.recommendations[{i}]"; _exact_keys(rec, {"title", "body", "candidate_id", "source_ids", "basis"}, path)
        candidate_id = _string(rec["candidate_id"], f"{path}.candidate_id")
        if candidate_id in seen: _fail("report recommendation candidate_id must be distinct")
        seen.add(candidate_id)
        if ":" not in candidate_id: _fail(f"{path}.candidate_id invalid")
        prefix, cid = candidate_id.split(":", 1); candidate = pools.get(prefix, {}).get(cid)
        if candidate is None: _fail(f"{path}.candidate_id unresolved")
        if rec["title"] != candidate["title"] or rec["body"] != candidate["body"]: _fail(f"{path} must preserve candidate title/body")
        expected_sources = [f"{prefix}:{source_id}" for source_id in candidate["source_ids"]]
        if rec["source_ids"] != expected_sources: _fail(f"{path}.source_ids must match candidate")
        basis = _obj(rec["basis"], f"{path}.basis")
        if set(basis) != {"quote", "start_ms", "analysis"} or not _string(basis.get("analysis"), f"{path}.basis.analysis"): _fail(f"{path}.basis invalid")
        if (basis.get("quote"), basis.get("start_ms")) not in {_report_evidence(e) for e in candidate["evidence"]}: _fail(f"{path}.basis must be candidate evidence")


def validate_bundle(normalized, structure, logic, report=None):
    metadata = _obj(_obj(normalized, "normalized").get("metadata"), "normalized.metadata")
    if set(metadata) != META: _fail("normalized.metadata must have exact required keys")
    segments = _segments(normalized)
    struct = _validate_structure(_obj(structure, "structure"), metadata, segments)
    logical = _validate_logic(_obj(logic, "logic"), metadata, segments)
    if report is not None: _validate_report(report, struct, logical)


def main(argv=None):
    parser = argparse.ArgumentParser(usage="validate_passes.py NORMALIZED_JSON STRUCTURE_JSON LOGIC_JSON [REPORT_JSON]")
    parser.add_argument("normalized_json"); parser.add_argument("structure_json"); parser.add_argument("logic_json"); parser.add_argument("report_json", nargs="?")
    args = parser.parse_args(argv)
    try:
        paths = [args.normalized_json, args.structure_json, args.logic_json] + ([args.report_json] if args.report_json else [])
        values = [json.loads(Path(path).read_text(encoding="utf-8")) for path in paths]
        validate_bundle(*values)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr); return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
