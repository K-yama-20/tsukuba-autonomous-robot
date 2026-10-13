"""Positive and adversarial tests of the migration validator, not robot tests."""
import copy, json, sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from build_migration import schema
from validate_model import core, load_yaml, migration, DESIGN

FIXTURE=Path(__file__).with_name('fixtures')/'minimal.yaml'
class CoreTests(unittest.TestCase):
    def setUp(self): self.m=load_yaml(FIXTURE); self.s=schema()
    def codes(self,m): return [x['code'] for x in core(m,self.s)[0]]
    def test_valid_minimal(self): self.assertEqual(self.codes(self.m),[])
    def test_bad_fixture_cases(self):
        cases=json.loads(FIXTURE.with_name('violations.json').read_text())
        for case in cases:
            with self.subTest(case=case['name']):
                m=copy.deepcopy(self.m)
                if case['operation']=='duplicate_entity': m['entities'].append(copy.deepcopy(m['entities'][0]))
                elif case['operation']=='set_related_refs': m['entities'][0]['related_refs']=case['value']
                elif case['operation']=='clear_source_refs': m['entities'][0]['source_refs']=[]
                self.assertIn(case['expected_code'],self.codes(m))
    def test_source_binding_missing_field(self):
        self.m['entities'][0]['field_bindings']['statement']['field']='missing'
        self.assertIn('FIELD_SOURCE',self.codes(self.m))
    def test_source_ref_points_to_entity(self):
        self.m['entities'][0]['source_refs']=['R-1']
        self.assertIn('SOURCE_TARGET',self.codes(self.m))
    def test_unknown_schema_property(self):
        self.m['entities'][0]['unreviewed_flag']=True
        self.assertIn('SCHEMA',self.codes(self.m))
    def test_unknown_design_status(self):
        self.m['entities'][0]['design_status']='実車確認済み'
        self.assertIn('SCHEMA',self.codes(self.m))
    def test_unsubstantiated_approval(self):
        self.m['entities'][0]['design_status']='承認済み'
        self.assertIn('APPROVAL_EVIDENCE',self.codes(self.m))
    def test_cross_collection_duplicate_id(self):
        self.m['entities'][0]['id']='SRC-1'
        self.assertIn('DUPLICATE_ID',self.codes(self.m))
    def test_unknown_parameter_cannot_be_zero(self):
        e=self.m['entities'][0]; e['kind']='parameter'
        e['parameter']={'owner_ref':'R-1','value':0,'value_state':'unresolved','unit':None}
        self.assertIn('SCHEMA',self.codes(self.m))
    def test_human_issue_requires_options(self):
        e=self.m['entities'][0]; e['kind']='issue'
        e['issue']={'category':'human','state':'open','affected_refs':['R-1'],'resolution_refs':[],'question':'決定事項','next_action':'人が決める'}
        self.assertIn('SCHEMA',self.codes(self.m))
    def test_technical_issue_is_not_human_approval(self):
        e=self.m['entities'][0]; e['kind']='issue'
        e['issue']={'category':'technical','state':'open','affected_refs':['R-1'],'resolution_refs':[],'question':'技術設計','next_action':'AIが設計','options':[]}
        self.assertIn('SCHEMA',self.codes(self.m))
    def test_unbound_connection_requires_issue(self):
        e=self.m['entities'][0]; e['kind']='diagram_connection'
        e['diagram']={'object_kind':'edge','parent_ref':None,'from_ref':None,'to_ref':None,'label_refs':[],'module_match_refs':[],'endpoint_status':'bound'}
        self.assertIn('UNTRACKED_UNBOUND',self.codes(self.m))
    def test_open_conflict_requires_issue(self):
        e=self.m['entities'][0]; e['kind']='reconciliation'
        e['reconciliation']={'state':'open','affected_refs':['R-1'],'adopted_requirement_refs':[],'scope':'未決','rationale':'不明','issue_refs':[]}
        self.assertIn('UNTRACKED_CONFLICT',self.codes(self.m))
    def test_duplicate_yaml_mapping_key(self):
        from ruamel.yaml import YAML
        from ruamel.yaml.constructor import DuplicateKeyError
        y=YAML(typ='safe'); y.allow_duplicate_keys=False
        with self.assertRaises(DuplicateKeyError): y.load('id: A\nid: B\n')

class MigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m=load_yaml(DESIGN/'model.yaml'); cls.man=json.loads((DESIGN/'migration_manifest.json').read_text())
    def errors(self,m): return migration(m,self.man)[0]
    def test_real_model(self): self.assertEqual(self.errors(self.m),[])
    def test_deleted_legacy_mapping(self):
        m=copy.deepcopy(self.m); m['migration']['id_map'].pop(0)
        self.assertTrue(any('198 definition' in x['path'] or 'all ID map' in x['path'] for x in self.errors(m)))
    def test_raw_source_change(self):
        m=copy.deepcopy(self.m); s=next(s for s in m['sources'] if s['kind']=='excel_row'); s['raw_fields'][next(iter(s['raw_fields']))]='改変'
        self.assertTrue(any('Excel verbatim' in x['path'] for x in self.errors(m)))
    def test_lost_known_issue(self):
        m=copy.deepcopy(self.m); m['entities']=[e for e in m['entities'] if e['id']!='U-DRAW-001']
        self.assertTrue(any('known issue ID' in x['path'] for x in self.errors(m)))
    def test_guessed_drawio_target(self):
        m=copy.deepcopy(self.m); e=next(e for e in m['entities'] if e['kind']=='diagram_connection' and e['diagram']['to_ref'] is None)
        e['diagram']['to_ref']=e['diagram']['from_ref']; e['diagram']['endpoint_status']='bound'
        self.assertTrue(any('drawio endpoint' in x['path'] or 'unbound' in x['path'] for x in self.errors(m)))
    def test_derived_view_cannot_lose_owner_replacement(self):
        m=copy.deepcopy(self.m); e=next(e for e in m['entities'] if e['id']=='FM-M-025')
        e['related_refs']=[r for r in e['related_refs'] if not r.startswith('C-')]
        self.assertIn('LOST_OWNER_RECONCILIATION',[e['code'] for e in core(m,schema())[0]])

if __name__=='__main__': unittest.main(verbosity=2)
