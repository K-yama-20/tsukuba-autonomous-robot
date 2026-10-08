"""Positive and adversarial tests of the fidelity validator, not robot tests."""
import copy, json, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from model_schema import schema
from validate_model import core, load_yaml, migration, DESIGN

FIXTURE = Path(__file__).with_name('fixtures') / 'minimal.yaml'


class CoreTests(unittest.TestCase):
    def setUp(self): self.m = load_yaml(FIXTURE); self.s = schema()
    def codes(self, m): return [x['code'] for x in core(m, self.s)[0]]
    def test_valid_minimal(self): self.assertEqual(self.codes(self.m), [])
    def test_bad_fixture_cases(self):
        cases = json.loads(FIXTURE.with_name('violations.json').read_text())
        for case in cases:
            with self.subTest(case=case['name']):
                m = copy.deepcopy(self.m)
                if case['operation'] == 'duplicate_entity': m['entities'].append(copy.deepcopy(m['entities'][0]))
                elif case['operation'] == 'set_related_refs': m['entities'][0]['related_refs'] = case['value']
                elif case['operation'] == 'clear_source_refs': m['entities'][0]['source_refs'] = []
                self.assertIn(case['expected_code'], self.codes(m))
    def test_source_binding_missing_field(self):
        self.m['entities'][0]['field_bindings']['statement']['field'] = 'missing'
        self.assertIn('FIELD_SOURCE', self.codes(self.m))
    def test_source_ref_points_to_entity(self):
        self.m['entities'][0]['source_refs'] = ['R-1']
        self.assertIn('SOURCE_TARGET', self.codes(self.m))
    def test_unknown_schema_property(self):
        self.m['entities'][0]['unreviewed_flag'] = True
        self.assertIn('SCHEMA', self.codes(self.m))
    def test_unknown_design_status(self):
        self.m['entities'][0]['design_status'] = '実車確認済み'
        self.assertIn('SCHEMA', self.codes(self.m))
    def test_unsubstantiated_approval(self):
        self.m['entities'][0]['design_status'] = '承認済み'
        self.assertIn('APPROVAL_EVIDENCE', self.codes(self.m))
    def test_cross_collection_duplicate_id(self):
        self.m['entities'][0]['id'] = 'SRC-1'
        self.assertIn('DUPLICATE_ID', self.codes(self.m))
    def test_unknown_parameter_cannot_be_zero(self):
        e = self.m['entities'][0]; e['kind'] = 'parameter'
        e['parameter'] = {'owner_ref': 'R-1', 'value': 0, 'value_state': 'unresolved', 'unit': None}
        self.assertIn('SCHEMA', self.codes(self.m))
    def test_human_issue_requires_options(self):
        e = self.m['entities'][0]; e['kind'] = 'issue'
        e['issue'] = {'category': 'human', 'state': 'open', 'affected_refs': ['R-1'], 'resolution_refs': [], 'question': '決定事項', 'next_action': '人が決める'}
        self.assertIn('SCHEMA', self.codes(self.m))
    def test_technical_issue_is_not_human_approval(self):
        e = self.m['entities'][0]; e['kind'] = 'issue'
        e['issue'] = {'category': 'technical', 'state': 'open', 'affected_refs': ['R-1'], 'resolution_refs': [], 'question': '技術設計', 'next_action': 'AIが設計', 'options': []}
        self.assertIn('SCHEMA', self.codes(self.m))
    def test_unbound_connection_requires_issue(self):
        e = self.m['entities'][0]; e['kind'] = 'diagram_connection'
        e['diagram'] = {'object_kind': 'edge', 'parent_ref': None, 'from_ref': None, 'to_ref': None, 'label_refs': [], 'module_match_refs': [], 'endpoint_status': 'bound'}
        self.assertIn('UNTRACKED_UNBOUND', self.codes(self.m))
    def test_open_conflict_requires_issue(self):
        e = self.m['entities'][0]; e['kind'] = 'reconciliation'
        e['reconciliation'] = {'state': 'open', 'affected_refs': ['R-1'], 'adopted_requirement_refs': [], 'scope': '未決', 'rationale': '不明', 'issue_refs': []}
        self.assertIn('UNTRACKED_CONFLICT', self.codes(self.m))
    def test_duplicate_yaml_mapping_key(self):
        from ruamel.yaml import YAML
        from ruamel.yaml.constructor import DuplicateKeyError
        y = YAML(typ='safe'); y.allow_duplicate_keys = False
        with self.assertRaises(DuplicateKeyError): y.load('id: A\nid: B\n')
    # ---- revision / decision ledger rules (REV-002) ----
    def test_answered_decision_needs_verbatim(self):
        self.m['decisions'] = [{'id': 'DEC-X', 'kind': 'approval', 'status': 'answered', 'asked_on': None, 'answered_on': '2026-10-08', 'channel': 'chat', 'question': 'q', 'answer_verbatim': '  ', 'affected_refs': [], 'resulting_refs': [], 'note': ''}]
        self.assertIn('DECISION_NO_VERBATIM', self.codes(self.m))
    def test_revision_ref_requires_membership(self):
        self.m['revisions'] = [{'id': 'REV-X', 'date': 'd', 'summary': 's', 'basis_refs': [], 'added_entity_ids': [], 'modified_entity_ids': [], 'added_source_ids': [], 'added_file_ids': [], 'removed_entity_ids': []}]
        self.m['entities'][0]['revision_ref'] = 'REV-X'
        self.assertIn('REVISION_MEMBERSHIP', self.codes(self.m))
    def test_revision_cannot_delete(self):
        self.m['revisions'] = [{'id': 'REV-X', 'date': 'd', 'summary': 's', 'basis_refs': [], 'added_entity_ids': [], 'modified_entity_ids': [], 'added_source_ids': [], 'added_file_ids': [], 'removed_entity_ids': ['R-1']}]
        self.assertIn('SCHEMA', self.codes(self.m))
    def test_boundary_element_cannot_be_proposal(self):
        self.m['decisions'] = [{'id': 'DEC-X', 'kind': 'question', 'status': 'pending', 'asked_on': None, 'answered_on': None, 'channel': 'chat', 'question': 'q', 'answer_verbatim': '', 'affected_refs': [], 'resulting_refs': [], 'note': ''}]
        self.m['entities'][0]['boundary'] = {'status': '未確認', 'decision_ref': 'DEC-X', 'note': 'n'}
        self.m['entities'][0]['adoption'] = 'designed_proposal'
        self.assertIn('SCHEMA', self.codes(self.m))


    def test_resolved_issue_needs_evidence(self):
        e = self.m['entities'][0]; e['kind'] = 'issue'
        e['issue'] = {'category': 'technical', 'state': 'resolved', 'affected_refs': ['R-1'], 'resolution_refs': [], 'question': 'q', 'next_action': 'done'}
        self.assertIn('RESOLVED_WITHOUT_EVIDENCE', self.codes(self.m))
    def test_decision_resolution_needs_answered_decision(self):
        self.m['decisions'] = [{'id': 'DEC-X', 'kind': 'question', 'status': 'pending', 'asked_on': None, 'answered_on': None, 'channel': 'chat', 'question': 'q', 'answer_verbatim': '', 'affected_refs': [], 'resulting_refs': [], 'note': ''}]
        e = self.m['entities'][0]; e['kind'] = 'reconciliation'
        e['reconciliation'] = {'state': 'resolved_by_decision', 'decision_ref': 'DEC-X', 'affected_refs': ['R-1'], 'adopted_requirement_refs': [], 'scope': 's', 'rationale': 'r', 'issue_refs': []}
        self.assertIn('DECISION_RESOLUTION', self.codes(self.m))
    def test_approved_without_evidence(self):
        self.m['entities'][0]['design_status'] = '承認済み'; self.m['entities'][0]['adoption'] = 'approved'
        self.assertIn('APPROVAL_EVIDENCE', self.codes(self.m))

class MigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_yaml(DESIGN / 'model.yaml'); cls.man = json.loads((DESIGN / 'migration_manifest.json').read_text())
    def errors(self, m): return migration(m, self.man)[0]
    def test_real_model(self): self.assertEqual(self.errors(self.m), [])
    def test_deleted_legacy_mapping(self):
        m = copy.deepcopy(self.m); m['migration']['id_map'].pop(0)
        self.assertTrue(any('198 definition' in x['path'] or 'all ID map' in x['path'] for x in self.errors(m)))
    def test_raw_source_change(self):
        m = copy.deepcopy(self.m); s = next(s for s in m['sources'] if s['kind'] == 'excel_row'); s['raw_fields'][next(iter(s['raw_fields']))] = '改変'
        self.assertTrue(any('Excel verbatim' in x['path'] for x in self.errors(m)))
    def test_lost_known_issue(self):
        m = copy.deepcopy(self.m); m['entities'] = [e for e in m['entities'] if e['id'] != 'U-DRAW-001']
        self.assertTrue(any('known issue ID' in x['path'] for x in self.errors(m)))
    def test_guessed_drawio_target(self):
        m = copy.deepcopy(self.m); e = next(e for e in m['entities'] if e['kind'] == 'diagram_connection' and e['diagram']['to_ref'] is None)
        e['diagram']['to_ref'] = e['diagram']['from_ref']; e['diagram']['endpoint_status'] = 'bound'
        self.assertTrue(any('drawio endpoint' in x['path'] or 'unbound' in x['path'] for x in self.errors(m)))
    def test_derived_view_cannot_lose_owner_replacement(self):
        m = copy.deepcopy(self.m); e = next(e for e in m['entities'] if e['id'] == 'FM-M-025')
        e['related_refs'] = [r for r in e['related_refs'] if not r.startswith('C-')]
        self.assertIn('LOST_OWNER_RECONCILIATION', [e['code'] for e in core(m, schema())[0]])
    # ---- baseline protection across revisions ----
    def test_unrecorded_new_entity_detected(self):
        m = copy.deepcopy(self.m); e = copy.deepcopy(next(e for e in m['entities'] if e['kind'] == 'ros_node')); e['id'] = 'ND-UNRECORDED'; m['entities'].append(e)
        self.assertTrue(any('revision-added entity inventory' in x['path'] for x in self.errors(m)))
    def test_silent_modification_of_baseline_entity_detected(self):
        m = copy.deepcopy(self.m); e = next(e for e in m['entities'] if e['id'] == 'M-001'); e['interpretation'] = '黙って変更'
        self.assertTrue(any('changed only via recorded modifications' in x['path'] for x in self.errors(m)))
    def test_stale_modification_record_detected(self):
        m = copy.deepcopy(self.m); m['revisions'][-1]['modified_entity_ids'].append('M-001')
        self.assertTrue(any('actually differ from baseline' in x['path'] for x in self.errors(m)))
    def test_deleted_baseline_entity_detected(self):
        m = copy.deepcopy(self.m); m['entities'] = [e for e in m['entities'] if e['id'] != 'T-01']
        self.assertTrue(any('immutable initial entity ID inventory' in x['path'] for x in self.errors(m)))
    def test_intent_revision_tampering_detected(self):
        m = copy.deepcopy(self.m); m['authority_revisions'][-1]['added_lines'][-1]['text'] = '改変された追記'
        self.assertTrue(any('reproduced from archived copy' in x['path'] for x in self.errors(m)))
    def test_intent_revision_hiding_removed_line_detected(self):
        m = copy.deepcopy(self.m); m['authority_revisions'][-1]['removed_lines'] = [{'line': 1, 'text': 'x'}]
        self.assertTrue(any('removed line text recorded' in x['path'] or 'reproduced from archived copy' in x['path'] for x in self.errors(m)))
    def test_superseded_requirement_needs_intent_justification(self):
        m = copy.deepcopy(self.m); e = next(e for e in m['entities'] if e['id'] == 'RQ-I001'); e['adoption'] = 'superseded'
        self.assertTrue(any('superseded requirement justified' in x['path'] for x in self.errors(m)))


if __name__ == '__main__': unittest.main(verbosity=2)
