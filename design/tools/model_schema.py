"""Schema 1.1 of the staged lower-design model.

Built on the frozen 1.0 schema of the initial migration (build_migration.schema)
so that every 1.0 record stays valid, then extended for revision tracking,
authority (intent.md) versions, a decision ledger, and the first lower-design
entities (ros_node, designed_interface, designed transitions/state owners).

Form check only. Fidelity to the baseline, reference existence, and design
consistency are checked by validate_model.py and check_design.py. Passing is
not design approval and not vehicle verification.
"""
import copy, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_migration import schema as schema_v1_0  # noqa: E402

DESIGN = Path(__file__).resolve().parents[1]
MODES_EVENT_CLASSES = ['boot', 'pc_restart', 'map_start', 'map_end', 'start', 'pause', 'resume', 'end', 'goal_reached', 'nav_failure', 'fault_recovery', 'recovery_failed']


def schema():
    s = copy.deepcopy(schema_v1_0())
    text = {'type': 'string', 'minLength': 1}
    nullable = {'type': ['string', 'null']}
    ref = {'type': 'string', 'minLength': 1, 'description': 'Global ID; existence and target kind checked by validator.'}
    refs = {'type': 'array', 'items': ref, 'uniqueItems': True}

    def obj(props, required=None):
        return {'type': 'object', 'properties': props, 'required': list(props) if required is None else required, 'additionalProperties': False}

    s['properties']['schema_version'] = {'const': '1.1'}
    s['$id'] = 'urn:gouda:design-model:1.1'
    s['description'] = ('Schema validates form only. Baseline fidelity, revision tracking, references, evidence and design '
                        'consistency require validate_model.py and check_design.py. Passing is not design approval.')
    # metadata: model revision pointer (optional so that 1.0-shaped minimal fixtures stay usable)
    s['properties']['metadata']['properties']['model_revision'] = text
    # files: a superseded authority keeps its hash and points at the archived copy
    fi = s['properties']['files']['items']
    fi['properties']['role'] = {'enum': ['authority', 'authority_superseded', 'source', 'extraction', 'verification', 'evidence']}
    fi['properties']['superseded_by'] = ref
    fi['properties']['archived_copy'] = text
    # authority revisions: machine-checked diff between intent versions
    line = obj({'line': {'type': 'integer', 'minimum': 1}, 'text': {'type': 'string'}})
    s['properties']['authority_revisions'] = {'type': 'array', 'items': obj({
        'id': ref, 'file_ref': ref, 'previous_file_ref': nullable, 'sha256': {'type': 'string', 'pattern': '^[0-9a-f]{64}$'},
        'previous_sha256': {'type': ['string', 'null'], 'pattern': '^[0-9a-f]{64}$'}, 'archived_previous_copy': nullable,
        'added_lines': {'type': 'array', 'items': line}, 'removed_lines': {'type': 'array', 'items': line}, 'changed_lines': {'type': 'array', 'items': line},
        'instruction_expected_added_lines': {'type': 'integer', 'minimum': 0}, 'observed_added_lines': {'type': 'integer', 'minimum': 0},
        'decision_ref': nullable, 'requirement_refs': refs, 'note': {'type': 'string'}})}
    # revisions: additions and modifications after the frozen baseline; deletions are not allowed
    s['properties']['revisions'] = {'type': 'array', 'items': obj({
        'id': ref, 'date': text, 'summary': text, 'basis_refs': refs, 'added_entity_ids': refs, 'modified_entity_ids': refs,
        'added_source_ids': refs, 'added_file_ids': refs, 'removed_entity_ids': {'type': 'array', 'maxItems': 0}})}
    # decision ledger: human answers verbatim, pending questions, measurements
    s['properties']['decisions'] = {'type': 'array', 'items': obj({
        'id': ref, 'kind': {'enum': ['approval', 'measurement', 'confirmation', 'question']}, 'status': {'enum': ['answered', 'pending', 'recorded']},
        'asked_on': nullable, 'answered_on': nullable, 'channel': text, 'question': text, 'answer_verbatim': {'type': 'string'},
        'affected_refs': refs, 'resulting_refs': refs, 'note': {'type': 'string'},
        'disposition': {'enum': ['resolved_by_existing', 'gate3_bundle', 'open_human', 'technical_pending', 'fact_check_pending', 'answered']}},
        ['id', 'kind', 'status', 'asked_on', 'answered_on', 'channel', 'question', 'answer_verbatim', 'affected_refs', 'resulting_refs', 'note'])}
    # entities
    en = s['properties']['entities']['items']
    en['properties']['kind']['enum'] += ['ros_node', 'designed_interface']
    en['properties']['adoption']['enum'] += ['designed_proposal', 'approved']
    en['properties']['approval_decision_ref'] = ref
    en['properties']['requirement_refs'] = refs
    en['properties']['revision_ref'] = text
    en['properties']['boundary'] = obj({'status': {'enum': ['未確認']}, 'decision_ref': ref, 'note': text})
    en['properties']['ros_node'] = obj({
        'node_name': {'type': 'string', 'pattern': '^[a-z][a-z0-9_]*$'},
        'responsibilities': {'type': 'array', 'items': text, 'minItems': 1},
        'absorbs_module_refs': refs, 'active_in_mode_refs': dict(refs, minItems=1),
        'lifecycle': {'enum': ['lifecycle_node', 'plain_node', 'external', 'script', 'firmware', '未設計']},
        'process_group': nullable, 'publishes_refs': refs, 'subscribes_refs': refs, 'serves_refs': refs, 'calls_refs': refs,
        'owned_state_refs': refs, 'placement_rationale': text})
    en['properties']['designed_interface'] = obj({
        'transport': {'enum': ['topic', 'service', 'action', 'tf', 'file', 'parameter', 'serial']},
        'name': text, 'message_type': text, 'standard_type': {'type': 'boolean'}, 'custom_type_reason': nullable,
        'purpose': {'enum': ['command', 'data', 'diagnostic', 'configuration']},
        'owner_ref': nullable, 'publisher_refs': dict(refs, minItems=1), 'consumer_refs': refs,
        'unit': nullable, 'frame': nullable, 'time_semantics': text,
        'qos': obj({'reliability': {'enum': ['reliable', 'best_effort', 'not_applicable', 'unconfirmed']},
                    'durability': {'enum': ['volatile', 'transient_local', 'not_applicable', 'unconfirmed']},
                    'history_depth': {'type': ['integer', 'null'], 'minimum': 1}}),
        'version_dependency': obj({'status': {'enum': ['none', 'confirmed_upstream', 'confirmed_installed_version', 'unconfirmed']}, 'evidence': {'type': 'array', 'items': text}, 'note': {'type': 'string'}}),
        'legacy_refs': refs})
    en['properties']['transition'] = obj({
        'from_mode_ref': nullable, 'to_mode_ref': ref, 'event_class': {'enum': MODES_EVENT_CLASSES},
        'trigger': text, 'trigger_kind': {'enum': ['human', 'automatic', 'system']}, 'owner_ref': ref,
        'guard': text, 'actions': {'type': 'array', 'items': text, 'minItems': 1}})
    so = en['properties']['state_owner']
    so['properties']['state_items'] = {'type': 'array', 'items': obj({
        'name': text, 'description': text, 'persistence': {'enum': ['volatile', 'persisted']}, 'restore_scope': text}), 'minItems': 1}
    so['required'] = ['owner_ref']
    so['anyOf'] = [{'required': ['state_definition']}, {'required': ['state_items']}]
    rec = en['properties']['reconciliation']
    rec['properties']['state'] = {'enum': ['resolved_by_intent', 'resolved_by_decision', 'open']}
    rec['properties']['decision_ref'] = ref
    en['properties']['issue']['properties']['state'] = {'enum': ['open', 'deferred', 'partially_superseded', 'resolved']}
    rec['properties']['retained_scope'] = text
    rec['properties']['scope_within_intent'] = text
    rec['properties']['clarification'] = text
    tp = en['properties']['test']
    tp['properties'].update({'procedure': text, 'expected': text, 'observe': text, 'stage': text})
    pp = en['properties']['parameter']
    pp['properties'].update({'stage': nullable, 'purpose': nullable, 'measurement': nullable, 'decision_deadline': nullable,
                             'software_trial_value': {'type': ['number', 'string', 'boolean', 'null']}, 'software_trial_basis': nullable,
                             # RQ-I076: declarative settings. Where a value is declared, how it reaches the running system, and its type.
                             'declaration': {'enum': ['ros_parameter', 'bt_xml', 'launch_argument', 'config_yaml', 'firmware_config', 'model_declared', 'code_state_machine']},
                             'target': nullable, 'param_key': nullable, 'value_type': nullable,
                             'apply_timing': {'enum': ['launch', 'lifecycle_configure', 'runtime_set', 'start_request', 'build_time', 'not_applicable']}})
    pay = {'ros_node': 'ros_node', 'designed_interface': 'designed_interface'}
    en['allOf'] += [{'if': {'properties': {'kind': {'const': k}}}, 'then': {'required': [v]}} for k, v in pay.items()]
    # A boundary-unconfirmed element may not be presented as approved or as a designed proposal.
    en['allOf'].append({'if': {'required': ['boundary']}, 'then': {'properties': {'design_status': {'enum': ['未設計', '案']}, 'adoption': {'enum': ['unresolved', 'legacy_candidate', 'reference_only', 'partially_superseded']}}}})
    return s


def write(path=DESIGN / 'schema.json'):
    path.write_text(json.dumps(schema(), ensure_ascii=False, indent=2) + '\n')
    return path


if __name__ == '__main__':
    print('Wrote', write())
