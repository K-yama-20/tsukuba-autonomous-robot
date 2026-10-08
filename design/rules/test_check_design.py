"""Adversarial tests of the design-consistency rules (check_design.py), not robot tests.

Each test injects one deliberate violation into a copy of the real model and
asserts that the corresponding rule reports 違反. The real model itself is
expected to have zero 違反 (未判定 items are allowed and listed)."""
import copy, json, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from model_schema import schema
from check_design import run, RULES
from validate_model import load_yaml, DESIGN


class DesignRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load_yaml(DESIGN / 'model.yaml'); cls.s = schema(); cls.man = json.loads((DESIGN / 'migration_manifest.json').read_text())
    def res(self, m): return run(m, self.s, self.man)
    def ent(self, m, i): return next(e for e in m['entities'] if e['id'] == i)
    def test_real_model_has_no_violations(self):
        r = self.res(self.m)
        self.assertEqual({k: v['violations'] for k, v in r.items() if v['violations']}, {})
        self.assertEqual(len(r), len(RULES))
    def test_dangling_reference(self):
        m = copy.deepcopy(self.m); self.ent(m, 'ND-03')['ros_node']['publishes_refs'].append('IFD-NOPE')
        self.assertEqual(self.res(m)['DR-01']['result'], '違反')
    def test_missing_owner(self):
        m = copy.deepcopy(self.m); self.ent(m, 'IFD-16')['designed_interface']['owner_ref'] = None
        self.assertEqual(self.res(m)['DR-02']['result'], '違反')
    def test_state_owner_backlink(self):
        m = copy.deepcopy(self.m); self.ent(m, 'ND-03')['ros_node']['owned_state_refs'].remove('SO-01')
        self.assertEqual(self.res(m)['DR-02']['result'], '違反')
    def test_publisher_conflict_in_mode(self):
        m = copy.deepcopy(self.m); self.ent(m, 'IFD-18')['designed_interface']['publisher_refs'].append('ND-08')
        self.assertEqual(self.res(m)['DR-03']['result'], '違反')
    def test_tf_dual_publisher_same_mode(self):
        m = copy.deepcopy(self.m); self.ent(m, 'ND-06')['ros_node']['active_in_mode_refs'].append('MODE-AUTO')
        self.assertEqual(self.res(m)['DR-03']['result'], '違反')
    def test_fifth_mode(self):
        m = copy.deepcopy(self.m); e = copy.deepcopy(self.ent(m, 'MODE-PAUSE')); e['id'] = 'MODE-STOP'; e['mode']['current_name'] = '完全停止'; m['entities'].append(e)
        r = self.res(m); self.assertEqual(r['DR-04']['result'], '違反'); self.assertEqual(r['DR-09']['result'], '違反')
    def test_autonomy_entered_automatically(self):
        m = copy.deepcopy(self.m); self.ent(m, 'TR-05')['transition']['trigger_kind'] = 'automatic'
        self.assertEqual(self.res(m)['DR-04']['result'], '違反')
    def test_missing_required_event(self):
        m = copy.deepcopy(self.m); m['entities'] = [e for e in m['entities'] if e['id'] != 'TR-08']
        self.assertEqual(self.res(m)['DR-04']['result'], '違反')
    def test_boot_into_wrong_mode(self):
        m = copy.deepcopy(self.m); self.ent(m, 'TR-01')['transition']['to_mode_ref'] = 'MODE-AUTO'
        self.assertEqual(self.res(m)['DR-04']['result'], '違反')
    def test_requirement_coverage_gap(self):
        m = copy.deepcopy(self.m)
        for e in m['entities']:
            if 'requirement_refs' in e and 'RQ-I026' in e['requirement_refs']: e['requirement_refs'].remove('RQ-I026')
        r = self.res(m); self.assertEqual(r['DR-05']['result'], '違反'); self.assertEqual(r['DR-08']['result'], '違反')
    def test_estop_term_in_design(self):
        m = copy.deepcopy(self.m); self.ent(m, 'ND-11')['ros_node']['responsibilities'].append('非常停止ボタン押下検知で中立')
        self.assertEqual(self.res(m)['DR-06']['result'], '違反')
    def test_unconfirmed_boundary_used(self):
        m = copy.deepcopy(self.m); self.ent(m, 'M-014')['boundary'] = {'status': '未確認', 'decision_ref': 'DEC-021', 'note': 'test'}
        self.ent(m, 'ND-11')['ros_node']['absorbs_module_refs'].append('M-014')
        self.assertEqual(self.res(m)['DR-07']['result'], '違反')
    def test_contract_replaced(self):
        m = copy.deepcopy(self.m); self.ent(m, 'C-017')['reconciliation']['affected_refs'].append('RQ-I023')
        self.assertEqual(self.res(m)['DR-08']['result'], '違反')
    def test_new_human_approval_step(self):
        m = copy.deepcopy(self.m); self.ent(m, 'TR-13')['transition']['trigger_kind'] = 'human'
        self.assertEqual(self.res(m)['DR-09']['result'], '違反')
    def test_version_dependent_if_approved(self):
        m = copy.deepcopy(self.m); e = self.ent(m, 'IFD-38'); e['issue_refs'] = []  # IFD-35 は REV-012 で実車版照合済みになったため、版未照合の IFD-38 で検査する
        self.assertEqual(self.res(m)['DR-10']['result'], '違反')
    def test_generic_value_filled(self):
        m = copy.deepcopy(self.m); p = self.ent(m, 'PRM-08')['parameter']; p['value'] = 0.5; p['value_state'] = 'source_value'
        self.assertEqual(self.res(m)['DR-11']['result'], '違反')
    def test_whole_row_superseded(self):
        m = copy.deepcopy(self.m); self.ent(m, 'M-028')['adoption'] = 'superseded'
        self.assertEqual(self.res(m)['DR-12']['result'], '違反')
    def test_legacy_candidate_approved(self):
        m = copy.deepcopy(self.m); e = self.ent(m, 'M-014'); e['design_status'] = '承認済み'; e['approval_source_ref'] = e['source_refs'][0]; e.pop('boundary', None)
        self.assertEqual(self.res(m)['DR-12']['result'], '違反')
    def test_human_issue_without_ledger_entry(self):
        m = copy.deepcopy(self.m); e = copy.deepcopy(self.ent(m, 'H-008')); e['id'] = 'H-NOLEDGER'; m['entities'].append(e)
        self.assertEqual(self.res(m)['DR-14']['result'], '違反')
    def test_duplicate_parameter_declaration(self):
        m = copy.deepcopy(self.m); a = self.ent(m, 'PRM-08')['parameter']; b = self.ent(m, 'PRM-09')['parameter']
        b['target'] = a['target']; b['param_key'] = a['param_key']
        self.assertEqual(self.res(m)['DR-15']['result'], '違反')
    def test_parameter_without_declaration(self):
        m = copy.deepcopy(self.m); self.ent(m, 'PRM-08')['parameter'].pop('declaration')
        self.assertEqual(self.res(m)['DR-15']['result'], '違反')
    def test_generated_params_must_match_model(self):
        m = copy.deepcopy(self.m); self.ent(m, 'PRM-08')['parameter']['value'] = 0.71
        self.assertEqual(self.res(m)['DR-15']['result'], '違反')
    def test_legitimate_settings_not_flagged(self):
        # Same key in different targets is a legitimate separate declaration; approved literal next to its key is not a hardcode.
        m = copy.deepcopy(self.m); a = self.ent(m, 'PRM-08')['parameter']; b = self.ent(m, 'PRM-16')['parameter']
        b['param_key'] = a['param_key']  # different target (gouda_mode_manager vs gouda_motion_controller)
        r = self.res(m)['DR-15']
        self.assertEqual(r['violations'], [x for x in r['violations'] if 'が 2 回宣言' not in x])
        self.assertEqual(self.res(self.m)['DR-15']['result'], '合格')
    def test_five_metres_reused(self):
        m = copy.deepcopy(self.m); p = self.ent(m, 'PRM-11')['parameter']; p['value'] = 5.0; p['value_state'] = 'source_value'
        self.assertEqual(self.res(m)['DR-13']['result'], '違反')


if __name__ == '__main__': unittest.main(verbosity=2)
