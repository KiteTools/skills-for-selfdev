import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from validate_passes import validate_bundle  # noqa: E402


def normalized():
    return {
        "metadata": {"title": "Test", "source_url": "https://youtu.be/x", "duration_ms": 9_000, "source_format": "vtt"},
        "segments": [
            {"id": "h1", "speaker": "HOST", "start_ms": 0, "end_ms": 1_000, "text": "Host asks a complete question."},
            {"id": "g1", "speaker": "GUEST", "start_ms": 1_000, "end_ms": 5_000, "text": "Guest provides a complete grounded statement here."},
            {"id": "g2", "speaker": "GUEST", "start_ms": 5_000, "end_ms": 8_000, "text": "Guest provides another complete grounded statement here."},
        ],
    }


def ev(index=1):
    return {"quote": "Guest provides a complete grounded statement here", "start_ms": 1_000, "segment_id": "g1"}


def ev2():
    return {"quote": "Guest provides another complete grounded statement here", "start_ms": 5_000, "segment_id": "g2"}


def ev3():
    return {"quote": "Guest provides a third complete grounded statement here", "start_ms": 8_000, "segment_id": "g3"}


def structure(doc):
    meta = copy.deepcopy(doc["metadata"])
    obs = {"id": "s1", "kind": "transition", "topic_ids": ["topic"], "analysis": "A structural move.", "evidence": [ev()]}
    return {
        "schema_version": "1.0", "pass": "structure", "input": {"normalized_metadata": meta, "guest_label": "GUEST"},
        "structural_chaos": {"score": 5.5, "rationale": "Two observations support this score.", "evidence": [ev(), {"quote": "Guest provides another complete grounded statement here", "start_ms": 5_000, "segment_id": "g2"}]},
        "topics": [{"id": "topic", "label": "Topic", "color": "#123456", "spans": [{"start_ms": 1_000, "end_ms": 8_000, "weight": "dominant", "note": "Topic span."}]}],
        "observations": [obs, {**copy.deepcopy(obs), "id": "s2", "kind": "return", "evidence": [ev2()]}],
        "recommendation_candidates": [
            {"id": f"sr{i}", "title": f"S {i}", "body": "Concrete structural revision.", "source_ids": ["s1"], "evidence": [ev()]}
            for i in range(1, 4)
        ],
        "uncertainties": [{"id": "su1", "target_ids": ["s1"], "reason": "Boundary is uncertain.", "impact": "low"}],
    }


def logic(doc):
    meta = copy.deepcopy(doc["metadata"])
    obs = {"id": "l1", "kind": "claim_chain", "analysis": "A claim chain.", "evidence": [ev()]}
    thesis = {"id": "t1", "claim": "Claim.", "status": "supported", "premises": ["Premise."], "evidence": [ev()], "conclusion": "Conclusion.", "observation_ids": ["l1"]}
    defect = {"id": "d1", "category": "unsupported_claim", "analysis": "Missing support.", "evidence": [ev()], "observation_ids": ["l1"]}
    strong = {"id": "m1", "title": "Strong", "analysis": "Clear chain.", "evidence": [ev()], "observation_ids": ["l1"]}
    return {
        "schema_version": "1.0", "pass": "logic", "input": {"normalized_metadata": meta, "guest_label": "GUEST"},
        "logical_soundness": {"score": 6.0, "rationale": "A qualified mixed assessment.", "evidence": [ev()]}, "observations": [obs], "theses": [thesis], "defects": [defect], "strong_moments": [strong],
        "recommendation_candidates": [
            {"id": f"lr{i}", "title": f"L {i}", "body": "Concrete logic revision.", "source_ids": ["d1"], "evidence": [ev()]}
            for i in range(1, 4)
        ], "uncertainties": [{"id": "lu1", "target_ids": ["l1"], "reason": "Term is broad.", "impact": "low"}],
    }


def report(doc, struct, log):
    candidates = [("structure", c) for c in struct["recommendation_candidates"]] + [("logic", c) for c in log["recommendation_candidates"]]
    chosen = candidates[:5]
    return {
        "metadata": copy.deepcopy(doc["metadata"]), "metrics": {},
        "scores": {"structural_chaos": struct["structural_chaos"]["score"], "logical_soundness": log["logical_soundness"]["score"]},
        "diagnosis": {"title": "D", "paragraphs": ["D"], "anchor_evidence": {"quote": ev()["quote"], "start_ms": 1_000}},
        "topics": copy.deepcopy(struct["topics"]),
        "structure": {"counts": [], "events": [{"kind": o["kind"], "quote": o["evidence"][0]["quote"], "start_ms": o["evidence"][0]["start_ms"], "analysis": o["analysis"]} for o in struct["observations"]]},
        "logic": {"defects": [{"category": d["category"], "count": 1, "example": {"quote": d["evidence"][0]["quote"], "start_ms": 1_000, "analysis": d["analysis"]}} for d in log["defects"]], "theses": [{"thesis": t["claim"], "status": t["status"], "support": t["conclusion"], "quote": t["evidence"][0]["quote"], "start_ms": 1_000} for t in log["theses"]], "strong_moments": [{"title": m["title"], "quote": m["evidence"][0]["quote"], "start_ms": 1_000, "analysis": m["analysis"]} for m in log["strong_moments"]]},
        "recommendations": [{"title": c["title"], "body": c["body"], "candidate_id": f"{p}:{c['id']}", "source_ids": [f"{p}:{x}" for x in c["source_ids"]], "basis": {"quote": c["evidence"][0]["quote"], "start_ms": c["evidence"][0]["start_ms"], "analysis": "Grounded basis."}} for p, c in chosen], "method": "Method."
    }


class ValidatePassesTests(unittest.TestCase):
    def setUp(self):
        self.doc = normalized(); self.struct = structure(self.doc); self.log = logic(self.doc); self.rep = report(self.doc, self.struct, self.log)

    def test_accepts_valid_passes_and_report_mapping(self):
        validate_bundle(self.doc, self.struct, self.log, self.rep)

    def test_rejects_extra_pass_property(self):
        self.struct["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "additional"):
            validate_bundle(self.doc, self.struct, self.log)

    def test_rejects_host_evidence_even_when_quote_exists(self):
        self.struct["observations"][0]["evidence"][0] = {"quote": "Host asks a complete question.", "start_ms": 0, "segment_id": "h1"}
        with self.assertRaisesRegex(ValueError, "GUEST"):
            validate_bundle(self.doc, self.struct, self.log)

    def test_rejects_mismatched_metadata(self):
        self.log["input"]["normalized_metadata"]["title"] = "Forged"
        with self.assertRaisesRegex(ValueError, "normalized_metadata"):
            validate_bundle(self.doc, self.struct, self.log)

    def test_rejects_report_candidate_source_that_does_not_match_candidate(self):
        self.rep["recommendations"][0]["source_ids"] = ["structure:s2"]
        with self.assertRaisesRegex(ValueError, "source_ids"):
            validate_bundle(self.doc, self.struct, self.log, self.rep)

    def test_rejects_report_basis_not_in_candidate_evidence(self):
        self.rep["recommendations"][0]["basis"]["start_ms"] = 5_000
        with self.assertRaisesRegex(ValueError, "basis"):
            validate_bundle(self.doc, self.struct, self.log, self.rep)

    def test_rejects_forged_qualified_candidate_id(self):
        self.rep["recommendations"][0]["candidate_id"] = "logic:sr1"
        with self.assertRaisesRegex(ValueError, "candidate_id"):
            validate_bundle(self.doc, self.struct, self.log, self.rep)

    def test_accepts_any_representative_evidence_from_a_structure_observation(self):
        alternate = {"quote": "Guest provides another complete grounded statement here", "start_ms": 5_000, "segment_id": "g2"}
        self.struct["observations"][0]["evidence"].append(alternate)
        self.rep["structure"]["events"][0]["quote"] = alternate["quote"]
        self.rep["structure"]["events"][0]["start_ms"] = alternate["start_ms"]
        validate_bundle(self.doc, self.struct, self.log, self.rep)

    def test_accepts_any_representative_evidence_from_logic_mapping(self):
        alternate = {"quote": "Guest provides another complete grounded statement here", "start_ms": 5_000, "segment_id": "g2"}
        self.log["theses"][0]["evidence"].append(alternate)
        self.rep["logic"]["theses"][0]["quote"] = alternate["quote"]
        self.rep["logic"]["theses"][0]["start_ms"] = alternate["start_ms"]
        validate_bundle(self.doc, self.struct, self.log, self.rep)

    def test_accepts_quote_spanning_contiguous_guest_segments_from_its_starting_segment(self):
        cross_segment = {"quote": "a complete grounded statement here. Guest provides", "start_ms": 1_000, "segment_id": "g1"}
        self.struct["observations"][0]["evidence"][0] = cross_segment
        self.struct["structural_chaos"]["evidence"] = [cross_segment, ev2()]
        validate_bundle(self.doc, self.struct, self.log)

    def test_rejects_cross_segment_quote_when_segment_id_is_not_the_starting_segment(self):
        self.struct["observations"][0]["evidence"][0] = {"quote": "a complete grounded statement here. Guest provides", "start_ms": 5_000, "segment_id": "g2"}
        with self.assertRaisesRegex(ValueError, "starting GUEST"):
            validate_bundle(self.doc, self.struct, self.log)

    def test_accepts_final_guest_segment_with_unknown_end(self):
        self.doc["segments"][-1]["end_ms"] = None
        self.struct["observations"][0]["evidence"][0] = {"quote": "Guest provides another complete grounded statement here", "start_ms": 5_000, "segment_id": "g2"}
        self.struct["observations"][1]["evidence"] = [ev()]
        self.struct["structural_chaos"]["evidence"] = [ev2(), ev()]
        validate_bundle(self.doc, self.struct, self.log)

    def test_rejects_non_distinct_structure_score_evidence_above_four(self):
        self.struct["structural_chaos"]["evidence"] = [ev(), ev()]
        with self.assertRaisesRegex(ValueError, "structure score evidence threshold"):
            validate_bundle(self.doc, self.struct, self.log)

    def test_rejects_structure_score_evidence_that_is_not_observation_evidence(self):
        self.struct["observations"][1]["evidence"] = [ev()]
        with self.assertRaisesRegex(ValueError, "structure score evidence.*observation"):
            validate_bundle(self.doc, self.struct, self.log)

    def test_rejects_three_structure_score_evidences_backed_by_only_two_observation_fingerprints(self):
        self.doc["segments"].append({"id": "g3", "speaker": "GUEST", "start_ms": 8_000, "end_ms": 9_000, "text": "Guest provides a third complete grounded statement here."})
        self.struct["observations"][1] = {**copy.deepcopy(self.struct["observations"][0]), "id": "s2"}
        self.struct["observations"].append({**copy.deepcopy(self.struct["observations"][0]), "id": "s3", "kind": "return", "evidence": [ev2(), ev3()]})
        self.struct["structural_chaos"]["score"] = 7
        self.struct["structural_chaos"]["evidence"] = [ev(), ev2(), ev3()]
        with self.assertRaisesRegex(ValueError, "structure score evidence threshold"):
            validate_bundle(self.doc, self.struct, self.log)

    def test_rejects_structure_score_seven_without_three_distinct_evidences(self):
        self.struct["observations"].append({**copy.deepcopy(self.struct["observations"][0]), "id": "s3", "kind": "loop"})
        self.struct["structural_chaos"]["score"] = 7
        with self.assertRaisesRegex(ValueError, "structure score evidence threshold"):
            validate_bundle(self.doc, self.struct, self.log)

    def test_rejects_logic_score_above_seven_without_two_distinct_strong_moments(self):
        self.log["logical_soundness"]["score"] = 8
        with self.assertRaisesRegex(ValueError, "logic score threshold"):
            validate_bundle(self.doc, self.struct, self.log)

    def test_rejects_logic_score_above_seven_with_cloned_strong_moments(self):
        self.log["logical_soundness"]["score"] = 8
        self.log["strong_moments"].append({**copy.deepcopy(self.log["strong_moments"][0]), "id": "m2"})
        with self.assertRaisesRegex(ValueError, "logic score threshold"):
            validate_bundle(self.doc, self.struct, self.log)

    def test_rejects_fabricated_thesis_status_or_support(self):
        for field, value in (("status", "unsupported"), ("support", "Fabricated support.")):
            with self.subTest(field=field):
                report = copy.deepcopy(self.rep)
                report["logic"]["theses"][0][field] = value
                with self.assertRaisesRegex(ValueError, "theses mapping"):
                    validate_bundle(self.doc, self.struct, self.log, report)

    def test_rejects_fabricated_strong_moment_or_defect_analysis(self):
        for path in (("strong_moments", 0, "analysis"), ("defects", 0, "example", "analysis")):
            with self.subTest(path=path):
                report = copy.deepcopy(self.rep)
                target = report["logic"][path[0]][path[1]]
                if len(path) == 4:
                    target = target[path[2]]
                    target[path[3]] = "Fabricated analysis."
                else:
                    target[path[2]] = "Fabricated analysis."
                with self.assertRaisesRegex(ValueError, "mapping"):
                    validate_bundle(self.doc, self.struct, self.log, report)

    def test_rejects_ids_reused_between_pass_collections(self):
        self.struct["recommendation_candidates"][0]["id"] = "s1"
        with self.assertRaisesRegex(ValueError, "duplicate id"):
            validate_bundle(self.doc, self.struct, self.log)

    def test_cli_returns_exit_two_not_typeerror_for_malformed_segment_bounds(self):
        self.doc["segments"][1]["start_ms"] = "not-a-number"
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            paths = []
            for name, value in (("normalized.json", self.doc), ("structure.json", self.struct), ("logic.json", self.log)):
                path = directory / name
                path.write_text(json.dumps(value), encoding="utf-8")
                paths.append(path)
            result = subprocess.run([sys.executable, str(SCRIPTS / "validate_passes.py"), *map(str, paths)], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertTrue(result.stderr.startswith("error: "))
        self.assertNotIn("Traceback", result.stderr)
