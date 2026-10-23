"""Checks of the troubleshooting ledger design/troubleshooting/ledger.yaml (DEC-321): schema, unique ids, fixed key
order, and that every referenced id exists in design/model.yaml."""
import json
import unittest
from pathlib import Path

import jsonschema
import yaml

DESIGN = Path(__file__).resolve().parents[1]
LEDGER = DESIGN / 'troubleshooting' / 'ledger.yaml'
SCHEMA = DESIGN / 'troubleshooting' / 'schema.json'
KEY_ORDER = ['id', 'name', 'status', 'sensitivity', 'decision_refs', 'related_refs', 'symptom', 'mechanism',
             'how_to_confirm', 'countermeasures', 'source', 'recorded_on', 'occurrences']


def model_ids():
    model = yaml.safe_load((DESIGN / 'model.yaml').read_text(encoding='utf-8'))
    ids = {e['id'] for e in model.get('entities', [])}
    ids |= {d['id'] for d in model.get('decisions', [])}
    return ids


class TroubleshootingLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = yaml.safe_load(LEDGER.read_text(encoding='utf-8'))
        cls.schema = json.loads(SCHEMA.read_text(encoding='utf-8'))

    def test_schema(self):
        jsonschema.validate(self.ledger, self.schema)

    def test_unique_ids(self):
        ids = [e['id'] for e in self.ledger['entries']]
        self.assertEqual(len(ids), len(set(ids)), ids)

    def test_key_order(self):
        for e in self.ledger['entries']:
            self.assertEqual(list(e.keys()), KEY_ORDER, e['id'])

    def test_references_exist_in_model(self):
        known = model_ids()
        for e in self.ledger['entries']:
            for ref in e['decision_refs'] + e['related_refs']:
                self.assertIn(ref, known, f"{e['id']}: {ref} is not in design/model.yaml")

    def test_schema_rejects_unknown_status(self):
        bad = {'entries': [dict(self.ledger['entries'][0], status='unknown')]}
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(bad, self.schema)


if __name__ == '__main__':
    unittest.main()
