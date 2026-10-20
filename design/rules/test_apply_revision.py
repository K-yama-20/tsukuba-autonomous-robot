"""Tests of apply_revision.py --dry-run --check (REV-120, DEC-187), not robot tests.

The change sets are written to a temporary directory; the canonical model is only read. Checked:
(1) a correct change set gives no new violation and leaves model.yaml and schema.json unchanged;
(2) two record errors of 第70〜82便 (handover_2026-10-21.md §3) come out as new violations (exit decision: fail):
    an entity with empty source_refs, and approval_decision_ref pointing at a recorded (not answered) decision;
(3) findings the current model already has (DR-04 / 05 / 10 / 11 / 15 undetermined) are not counted as new.
"""
import contextlib, hashlib, io, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import apply_revision as ar  # noqa: E402
from ruamel.yaml import YAML  # noqa: E402

DESIGN = Path(__file__).resolve().parents[1]
HEADER = "date: '2026-10-21'\nsummary: unit test of --dry-run --check (not applied)\nbasis_refs: []\nintent_version_copy: design/baselines/intent_history/intent_v13_c4d1a69aee5f.md\nfiles: []\ndecisions: []\ndecision_updates: []\n"


def digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class DryRunCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(); cls.dir = Path(cls.tmp.name)
        model = YAML(typ='safe').load((DESIGN / 'model.yaml').read_text())
        cls.prm = next(e for e in model['entities'] if e['id'] == 'PRM-78')
        cls.recorded = next(d['id'] for d in model['decisions'] if d.get('status') == 'recorded')
        cls.files = [DESIGN / 'model.yaml', DESIGN / 'schema.json']

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_set(self, rev_id, body):
        (self.dir / f'{rev_id}.yaml').write_text(f'id: {rev_id}\n' + HEADER + body)
        before = [digest(p) for p in self.files]
        with contextlib.redirect_stdout(io.StringIO()):
            s = ar.apply(rev_id, dry_run=True, check=True, revisions_dir=self.dir)
        self.assertEqual([digest(p) for p in self.files], before, 'the dry run must not write the model or the schema')
        return s

    def test_correct_change_set_has_no_new_finding(self):
        s = self.run_set('REV-9901', 'entities: []\nmodifications:\n- id: PRM-78\n  interpretation_append: unit test only\n')
        self.assertEqual(s['modified_entities'], 1)
        self.assertEqual(s['new_findings'], {}, 'existing undetermined items and the generated/params hash must not be counted')
        self.assertFalse(ar.has_new_violations(s))

    def test_empty_source_refs_is_a_new_violation(self):
        e = dict(self.prm, id='PRM-9901', source_refs=[], revision_ref='REV-9902')
        buf = io.StringIO(); YAML().dump({'entities': [e]}, buf)
        s = self.run_set('REV-9902', buf.getvalue() + 'modifications: []\n')
        self.assertTrue(ar.has_new_violations(s))
        self.assertTrue(any("'source_refs'" in v and 'non-empty' in v for v in s['new_findings']['DR-01']['violations']))

    def test_recorded_decision_as_approval_basis_is_a_new_violation(self):
        s = self.run_set('REV-9903', f'entities: []\nmodifications:\n- id: PRM-78\n  set:\n    approval_decision_ref: {self.recorded}\n')
        self.assertTrue(ar.has_new_violations(s))
        self.assertTrue(any('APPROVAL_EVIDENCE PRM-78' in v for v in s['new_findings']['DR-01']['violations']))

    def test_undetermined_alone_does_not_fail(self):
        self.assertFalse(ar.has_new_violations({'new_findings': {'DR-11': {'violations': [], 'undetermined': ['x']}}}))
        self.assertTrue(ar.has_new_violations({'new_findings': {'DR-01': {'violations': ['x'], 'undetermined': []}}}))


if __name__ == '__main__':
    unittest.main()
