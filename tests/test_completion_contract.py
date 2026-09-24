"""E1.0 Completion Contract kernel: pure contract, verifier and legality semantics."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from runtime.kernel import citation, completion, journal, review
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.contracts import accept_task_request, message, validate_spec
from runtime.kernel.execution import evaluate
from runtime.kernel.workspace import legacy_receipt

import completion_fixtures as fx

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / 'experiments/personal-agent-hub/e1-design/contract-examples.json'
TASK = 'task-e10'


def ref(task, label):
    return f'artifact://{task}/sha256:' + hashlib.sha256(label.encode()).hexdigest()


def contract(criteria, task=TASK, **payload):
    return message('CompletionContract', {'task_id': task, 'revision': 0, 'previous_ref': None,
        'amendment_ref': None, 'task_type': {'template': 'investigation', 'version': 1},
        'criteria': criteria, **payload})


def user_digest(criterion_id='user-1', level='REQUIRED', source='user', sha=None):
    return {'id': criterion_id, 'requirement': 'Exact deliverable.', 'level': level,
            'provenance': {'source': source},
            'verifier': {'kind': 'artifact_digest', 'version': 1, 'artifact': 'answer',
                         'sha256': sha or hashlib.sha256(b'GOOD').hexdigest()}}


def policy_criterion(criterion_id='canonical-build', source='project_policy', level='REQUIRED'):
    provenance = {'source': source, 'ref': 'orchid-policy#' + criterion_id, 'source_digest': 'sha256:' + 'b' * 64}
    if source == 'project_policy':
        provenance['designation_ref'] = ref(TASK, 'designation')
    return {'id': criterion_id, 'requirement': 'Canonical rule holds.', 'level': level, 'provenance': provenance,
            'verifier': {'kind': 'artifact_digest', 'version': 1, 'artifact': 'build',
                         'sha256': hashlib.sha256(b'PASS').hexdigest()}}


class Store:
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = ArtifactStore(Path(directory.name) / 'artifacts')


class ContractValidation(unittest.TestCase):
    def test_design_investigation_fixture_validates_and_e1d_schemas_are_explicitly_deferred(self):
        examples = json.loads(DESIGN.read_text())['contracts']
        investigation = examples[0]
        accepted = completion.validate_contract(investigation, 'task-example-investigation', mutating=False)
        self.assertEqual([c['level'] for c in accepted['criteria']].count('REQUIRED'), 5)
        for other in examples[1:]:
            with self.subTest(template=other['payload']['task_type']['template']), \
                    self.assertRaisesRegex(ValueError, 'schema is not implemented'):
                completion.validate_contract(other, other['payload']['task_id'], mutating=False)

    def test_design_amendment_example_is_admissible_user_change(self):
        examples = json.loads(DESIGN.read_text())
        base = completion.validate_contract(examples['contracts'][0], 'task-example-investigation', False)
        request = examples['amendment_example']['payload']
        submitted = fx.amendment('task-example-investigation', request['operations'])
        state = {'contract_ref': ref('task-example-investigation', 'r0'), 'human_responses': {}}
        actor, content = completion.validate_amendment_submission(submitted, 'task-example-investigation')
        amendment, updated = completion.apply_amendment(
            base, state['contract_ref'], actor, content, ref('task-example-investigation', 'action'), state, mutating=False)
        self.assertEqual(updated['revision'], 1)
        self.assertEqual(updated['criteria'][-1]['id'], 'user-accepts')
        self.assertEqual(amendment['actor']['kind'], 'user')

    def test_derived_provenance_never_creates_required_criteria(self):
        for source in ('repository', 'memory', 'model'):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, 'only create ADVISORY'):
                completion.validate_contract(contract([user_digest(), user_digest('d', source=source)]), TASK, False)
            advisory = completion.validate_contract(
                contract([user_digest(), user_digest('d', level='ADVISORY', source=source)]), TASK, False)
            self.assertEqual(advisory['criteria'][1]['level'], 'ADVISORY')

    def test_project_policy_requires_designation_and_pinned_digest(self):
        completion.validate_contract(contract([policy_criterion()]), TASK, False)
        for key in ('designation_ref', 'source_digest', 'ref'):
            bad = policy_criterion()
            del bad['provenance'][key]
            with self.subTest(missing=key), self.assertRaises(ValueError):
                completion.validate_contract(contract([bad]), TASK, False)
        claimed = user_digest()
        claimed['provenance']['designation_ref'] = ref(TASK, 'designation')
        with self.assertRaises(ValueError):  # content claiming designation is not designation
            completion.validate_contract(contract([claimed]), TASK, False)

    def test_invariant_only_on_task_type_and_template_must_match(self):
        bad = user_digest()
        bad['provenance']['invariant'] = True
        with self.assertRaises(ValueError):
            completion.validate_contract(contract([bad]), TASK, False)
        wrong = fx.journal_criterion('no-mutation', [{'name': 'admitted_before_observed'}], template='other@1')
        with self.assertRaisesRegex(ValueError, 'template'):
            completion.validate_contract(contract([wrong]), TASK, False)

    def test_closed_verifier_taxonomy_and_status_is_never_contract_data(self):
        for kind in ('capability_result', 'change_set', 'script', 'worker_says_done'):
            bad = user_digest()
            bad['verifier'] = {'kind': kind, 'version': 1}
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                completion.validate_contract(contract([bad]), TASK, False)
        with self.assertRaises(ValueError):
            completion.validate_contract(contract([{**user_digest(), 'status': 'satisfied'}]), TASK, False)
        with self.assertRaises(ValueError):
            completion.validate_contract(contract([user_digest(f'c{n}') for n in range(17)]), TASK, False)

    def test_unbound_required_only_without_mutating_authority(self):
        unbound = {**user_digest(), 'verifier': {'kind': 'unbound'}}
        completion.validate_contract(contract([unbound]), TASK, mutating=False)
        with self.assertRaisesRegex(ValueError, 'mutating authority'):
            completion.validate_contract(contract([unbound]), TASK, mutating=True)
        self.assertTrue(journal.mutating(['fixture.effect']))
        self.assertTrue(journal.mutating(['unknown.capability']))
        self.assertFalse(journal.mutating(['workspace.read', 'artifact.write', 'human.request']))

    def test_semantic_review_rules(self):
        base = [fx.lowered_c1(), fx.citation_criterion('findings-cited', [{'name': 'every_claim_cited'}])]
        completion.validate_contract(contract([*base, fx.semantic_criterion()]), TASK, False)
        with self.assertRaisesRegex(ValueError, 'REQUIRED semantic'):
            completion.validate_contract(contract([*base, fx.semantic_criterion(level='REQUIRED', source='user')]), TASK, False)
        with self.assertRaisesRegex(ValueError, 'REQUIRED semantic'):
            completion.validate_contract(contract([*base, fx.semantic_criterion(
                level='REQUIRED', on_low='request_human', artifact='review',
                request=fx.human_request(TASK, 'review-cause'))]), TASK, False)  # task_type provenance
        completion.validate_contract(contract([*base, fx.semantic_criterion(
            level='REQUIRED', source='user', on_low='request_human', artifact='review',
            request=fx.human_request(TASK, 'review-cause'))]), TASK, False)
        with self.assertRaisesRegex(ValueError, 'request_human requires'):
            completion.validate_contract(contract([*base, fx.semantic_criterion(on_low='request_human')]), TASK, False)
        deterministic = deepcopy(base)
        deterministic[1]['verifier']['subject'] = 'findings.conclusion'
        with self.assertRaisesRegex(ValueError, 'deterministically verified subject'):
            completion.validate_contract(contract([*deterministic, fx.semantic_criterion()]), TASK, False)
        with self.assertRaisesRegex(ValueError, 'depend only on deterministic'):
            completion.validate_contract(contract([*base, fx.semantic_criterion(depends=('missing',))]), TASK, False)

    def test_supersession_respects_precedence(self):
        low = user_digest('low', level='ADVISORY', source='model')
        low['superseded_by'] = 'high'
        completion.validate_contract(contract([user_digest('high'), low]), TASK, False)
        inverted = user_digest('high')
        inverted['superseded_by'] = 'low'
        with self.assertRaises(ValueError):
            completion.validate_contract(contract([inverted, user_digest('low', level='ADVISORY', source='model')]), TASK, False)
        invariant = fx.journal_criterion('no-mutation', [{'name': 'admitted_before_observed'}])
        invariant['superseded_by'] = 'high'
        with self.assertRaises(ValueError):
            completion.validate_contract(contract([user_digest('high'), invariant]), TASK, False)


class Intake(unittest.TestCase):
    def spec(self, parent=False):
        request = fx.human_request(TASK, 'decide')
        return validate_spec(message('TaskSpec', {'objective': 'Exact deliverable.', 'completion': [
            {'criterion': 'Exact', 'evidence': {'artifact': 'answer', 'sha256': 'a' * 64}},
            {'criterion': 'Decided', 'evidence': {'artifact': 'decision', 'verifier': 'human_response', 'request': request}}]}))

    def test_v0_lowering_is_revision_zero_with_user_or_parent_provenance(self):
        lowered = completion.lower_spec(self.spec(), TASK)
        self.assertEqual([c['id'] for c in lowered['criteria']], ['c1', 'c2'])
        self.assertEqual({c['level'] for c in lowered['criteria']}, {'REQUIRED'})
        self.assertEqual([c['verifier']['kind'] for c in lowered['criteria']], ['artifact_digest', 'human_response'])
        self.assertEqual(lowered['criteria'][0]['provenance'], {'source': 'user'})
        child = completion.lower_spec(self.spec(), TASK, {'task_id': 'parent', 'decision_id': 'parent/1', 'slot': None})
        self.assertEqual(child['criteria'][0]['provenance'], {'source': 'parent_task', 'ref': 'parent'})
        self.assertEqual(completion.accept_contract(self.spec(), None, None, TASK, False), lowered)

    def test_envelope_contract_must_carry_lowered_criteria_unchanged(self):
        spec = validate_spec(fx.investigation_spec())
        accepted = completion.accept_contract(spec, None, fx.investigation_contract(TASK), TASK, False)
        self.assertEqual(accepted['criteria'][0], fx.lowered_c1())
        dropped = fx.investigation_contract(TASK)
        dropped['payload']['criteria'] = dropped['payload']['criteria'][1:]
        weakened = fx.investigation_contract(TASK)
        weakened['payload']['criteria'][0]['level'] = 'ADVISORY'
        for bad in (dropped, weakened):
            with self.assertRaisesRegex(ValueError, 'unchanged'):
                completion.accept_contract(spec, None, bad, TASK, False)
        later = fx.investigation_contract(TASK)
        later['payload'].update(revision=1, previous_ref=ref(TASK, 'r0'), amendment_ref=ref(TASK, 'a'))
        with self.assertRaises(ValueError):
            completion.accept_contract(spec, None, later, TASK, False)

    def test_task_request_without_initial_action_requires_contract_and_grant(self):
        request = fx.investigation_request(TASK)
        del request['payload']['initial_action']
        accept_task_request(request, TASK)
        for missing in ('contract', 'grant'):
            bad = deepcopy(request)
            del bad['payload'][missing]
            with self.subTest(missing=missing), self.assertRaisesRegex(ValueError, 'contract and a grant'):
                accept_task_request(bad, TASK)


class Amendments(unittest.TestCase):
    def setUp(self):
        self.base = completion.validate_contract(contract([
            fx.journal_criterion('no-mutation', [{'name': 'admitted_before_observed'}]),
            user_digest('user-1'), policy_criterion(), policy_criterion('ops-rule', source='operator_rule'),
            {**user_digest('suggested', level='ADVISORY', source='memory'), 'requirement': 'Remembered preference.'},
        ]), TASK, False)
        self.state = {'contract_ref': ref(TASK, 'r0'), 'human_responses': {'decide': ref(TASK, 'response')}}

    def apply(self, operations, actor=None, from_revision=0, **content):
        actor, request = completion.validate_amendment_submission(
            fx.amendment(TASK, operations, from_revision=from_revision, actor=actor, **content), TASK)
        return completion.apply_amendment(self.base, self.state['contract_ref'], actor, request,
                                          ref(TASK, 'action'), self.state, mutating=False)

    def test_user_waiver_is_explicit_retained_and_keeps_the_criterion(self):
        amendment, updated = self.apply([{'op': 'waive', 'id': 'user-1', 'reason': 'Not needed any more.'}])
        waived = next(c for c in updated['criteria'] if c['id'] == 'user-1')
        self.assertEqual(waived['waiver']['revision'], 1)
        self.assertEqual(waived['waiver']['actor']['ref'], ref(TASK, 'action'))
        self.assertEqual(waived['waiver']['actor']['binding'], 'test-binding')
        self.assertEqual(len(updated['criteria']), len(self.base['criteria']))
        self.assertEqual(updated['previous_ref'], self.state['contract_ref'])
        self.assertEqual(amendment['from_revision'], 0)
        self.assertNotIn('waiver', next(c for c in self.base['criteria'] if c['id'] == 'user-1'))  # immutable r0

    def test_authority_matrix(self):
        pinned = {'exception_for': {'rule': 'orchid-policy#canonical-build', 'digest': 'sha256:' + 'b' * 64}}
        cases = [
            ('invariant waive by user', [{'op': 'waive', 'id': 'no-mutation', 'reason': 'x'}], fx.USER, {}, 'invariant'),
            ('invariant waive by operator', [{'op': 'waive', 'id': 'no-mutation', 'reason': 'x'}], fx.OPERATOR_EXCEPTION, pinned, 'invariant'),
            ('invariant rebind', [{'op': 'rebind', 'id': 'no-mutation', 'verifier': {'kind': 'capability_journal', 'version': 1,
                'predicates': [{'name': 'workspace_subset'}]}}], fx.USER, {}, 'invariant'),
            ('policy waive by user text', [{'op': 'waive', 'id': 'canonical-build', 'reason': 'skip'}], fx.USER, {}, 'policy exception'),
            ('policy exception names another rule', [{'op': 'waive', 'id': 'ops-rule', 'reason': 'x'}], fx.OPERATOR_EXCEPTION, pinned, 'different rule'),
            ('operator cannot waive user criteria', [{'op': 'waive', 'id': 'user-1', 'reason': 'x'}], fx.OPERATOR_EXCEPTION, pinned, 'only the user'),
            ('user cannot add policy criteria', [{'op': 'add', 'criterion': policy_criterion('new-rule')}], fx.USER, {}, 'cannot add'),
            ('project policy cannot waive', [{'op': 'waive', 'id': 'canonical-build', 'reason': 'x'}], fx.POLICY_UPDATE, {}, 'policy exception'),
        ]
        for name, operations, actor, content, reason in cases:
            with self.subTest(name), self.assertRaisesRegex(completion.AmendmentDenied, reason):
                self.apply(operations, actor, **content)
        _, updated = self.apply([{'op': 'waive', 'id': 'canonical-build', 'reason': 'CI outage'}], fx.OPERATOR_EXCEPTION, **pinned)
        waiver = next(c for c in updated['criteria'] if c['id'] == 'canonical-build')['waiver']
        self.assertEqual(waiver['actor']['exception_for']['rule'], 'orchid-policy#canonical-build')
        _, tightened = self.apply([{'op': 'add', 'criterion': policy_criterion('integration-suite')}], fx.POLICY_UPDATE)
        self.assertEqual(tightened['criteria'][-1]['provenance']['source'], 'project_policy')

    def test_policy_requirements_stay_pinned_to_their_source_digest(self):
        original = next(c for c in self.base['criteria'] if c['id'] == 'canonical-build')['provenance']
        edited = {'rule': 'orchid-policy#canonical-build', 'digest': 'sha256:' + 'c' * 64}  # policy file changed since
        with self.assertRaisesRegex(completion.AmendmentDenied, 'different rule or digest'):
            self.apply([{'op': 'waive', 'id': 'canonical-build', 'reason': 'x'}], fx.OPERATOR_EXCEPTION, exception_for=edited)
        newer = policy_criterion('canonical-build')
        newer['provenance']['source_digest'] = edited['digest']
        with self.assertRaisesRegex(ValueError, 'new id'):  # a later edit cannot replace the pinned criterion
            self.apply([{'op': 'add', 'criterion': newer}], fx.POLICY_UPDATE)
        _, updated = self.apply([{'op': 'waive', 'id': 'canonical-build', 'reason': 'x'}], fx.OPERATOR_EXCEPTION,
                                exception_for={'rule': original['ref'], 'digest': original['source_digest']})
        after = next(c for c in updated['criteria'] if c['id'] == 'canonical-build')
        self.assertEqual(after['provenance'], original)  # every revision still names the version that created it
        self.assertEqual(after['waiver']['actor']['exception_for'], {'rule': original['ref'], 'digest': original['source_digest']})

    def test_elevating_a_derived_suggestion_records_user_confirmation(self):
        _, updated = self.apply([{'op': 'elevate', 'id': 'suggested'}])
        elevated = next(c for c in updated['criteria'] if c['id'] == 'suggested')
        self.assertEqual((elevated['level'], elevated['provenance']),
                         ('REQUIRED', {'source': 'user', 'confirmed_from': 'memory'}))

    def test_stale_revision_and_unaccepted_human_action_are_rejected(self):
        via_response = {**fx.USER, 'via': 'human_response'}
        with self.assertRaises(completion.AmendmentConflict):
            self.apply([{'op': 'waive', 'id': 'user-1', 'reason': 'x'}], from_revision=1)
        with self.assertRaisesRegex(completion.AmendmentDenied, 'not accepted'):
            self.apply([{'op': 'waive', 'id': 'user-1', 'reason': 'x'}], via_response, response_ref=ref(TASK, 'forged'))
        _, updated = self.apply([{'op': 'waive', 'id': 'user-1', 'reason': 'x'}], via_response,
                                response_ref=ref(TASK, 'response'))
        self.assertEqual(updated['criteria'][1]['waiver']['actor']['response_ref'], ref(TASK, 'response'))

    def test_payload_cannot_claim_or_upgrade_the_actor(self):
        waive = [{'op': 'waive', 'id': 'canonical-build', 'reason': 'x'}]
        pinned = {'rule': 'orchid-policy#canonical-build', 'digest': 'sha256:' + 'b' * 64}
        forged = fx.amendment(TASK, waive)
        forged['payload']['amendment']['payload']['actor'] = {**fx.OPERATOR_EXCEPTION, 'exception_for': pinned}
        with self.assertRaisesRegex(ValueError, 'Invalid object fields'):  # content has no authority field
            completion.validate_amendment_submission(forged, TASK)
        with self.assertRaisesRegex(ValueError, 'policy exception names'):  # naming a rule is not being the operator
            completion.validate_amendment_submission(fx.amendment(TASK, waive, exception_for=pinned), TASK)
        bare = fx.amendment_content(TASK, waive)  # content without a binding's envelope
        with self.assertRaises(ValueError):
            completion.validate_amendment_submission(bare, TASK)
        for actor in ({'kind': 'model', 'via': 'modify-constraints', 'binding': 'b'},
                      {'kind': 'user', 'via': 'policy_exception', 'binding': 'b'},
                      {'kind': 'operator', 'via': 'policy_exception'}):  # no establishing binding
            with self.subTest(actor=actor), self.assertRaises(ValueError):
                completion.validate_amendment_submission(fx.amendment(TASK, waive, actor=actor, exception_for=pinned), TASK)
        with self.assertRaisesRegex(completion.AmendmentDenied, 'policy exception'):
            self.apply(waive)  # a user context stays user whatever the content says

    def test_request_shape_rejects_malformed_changes(self):
        for operation in ({'op': 'delete', 'id': 'user-1'}, {'op': 'waive', 'id': 'user-1'}):
            with self.assertRaises(ValueError):
                completion.validate_amendment_submission(fx.amendment(TASK, [operation]), TASK)
        with self.assertRaisesRegex(ValueError, 'superseded only by'):
            self.apply([{'op': 'supersede', 'id': 'user-1', 'by': 'user-1'}])
        with self.assertRaisesRegex(ValueError, 'superseded only by'):  # lower precedence cannot supersede
            self.apply([{'op': 'supersede', 'id': 'user-1', 'by': 'suggested'}])


class JournalFixtures(Store):
    def authority(self, capabilities=('workspace.read', 'artifact.write'), workspaces=(fx.WORKSPACE,)):
        value = journal.compile_authority(TASK, capabilities, workspaces, True)
        return self.store.put_json(TASK, value)

    def chain(self, entries):
        head, length = None, 0
        for entry in entries:
            head = journal.append(self.store, TASK, head, length, entry)
            length += 1
        return head, length

    def facts(self, entries, authority_ref):
        head, length = self.chain(entries)
        return completion.load_journal({'task_id': TASK, 'journal_head': head, 'journal_length': length,
                                        'authority_ref': authority_ref}, self.store)

    def admitted(self, op, capability, authority, workspace=None):
        entry = {'phase': 'admitted', 'decision_id': op, 'operation_id': op, 'capability': capability,
                 'operation_class': journal.operation_class(capability), 'provider': 'kernel', 'operation': capability,
                 'request_digest': 'sha256:' + 'c' * 64, 'authority_ref': authority, 'contract_revision': 0}
        return {**entry, 'workspace_id': workspace} if workspace else entry

    def observed(self, op, outcome='success'):
        return {'phase': 'observed', 'operation_id': op, 'outcome': outcome, 'receipt_ref': ref(TASK, op)}


class Journal(JournalFixtures, unittest.TestCase):
    def test_hash_chain_is_verified_and_tampering_is_unknown(self):
        authority = self.authority()
        head, length = self.chain([self.admitted('t/1', 'workspace.read', authority, fx.WORKSPACE), self.observed('t/1')])
        self.assertEqual([e['seq'] for _, e in journal.read(self.store, TASK, head, length)], [0, 1])
        with self.assertRaises(ValueError):
            journal.read(self.store, TASK, head, length + 1)
        facts = completion.load_journal({'task_id': TASK, 'journal_head': head, 'journal_length': 3}, self.store)
        self.assertIn('unreadable', facts['error'])

    def test_no_effect_predicates(self):
        authority = self.authority()
        predicates = [{'name': 'operation_classes_subset', 'allowed': ['workspace.read']}, {'name': 'admitted_before_observed'}]
        facts = self.facts([self.admitted('t/1', 'workspace.read', authority, fx.WORKSPACE), self.observed('t/1'),
                            self.admitted('t/2', 'artifact.write', authority), self.observed('t/2'),
                            {'phase': 'denied', 'decision_id': 't/3', 'capability': 'fixture.effect',
                             'operation_class': 'external.effect', 'provider': 'kernel', 'operation': 'fixture.effect',
                             'reason': 'Capability denied', 'authority_ref': authority, 'contract_revision': 0}], authority)
        status, detail = journal.verify(predicates, facts['analysis'], facts['authorities'])
        self.assertEqual(status, 'satisfied', detail)
        self.assertIn('1 denial', detail)
        self.assertEqual(journal.verify([{'name': 'workspace_subset'}], facts['analysis'], facts['authorities'])[0], 'satisfied')
        present = [{'name': 'observed_operation_present', 'operations': ['read_file']}]
        self.assertEqual(journal.verify(present, facts['analysis'], facts['authorities'])[0], 'pending')
        present = [{'name': 'observed_operation_present', 'operations': ['workspace.read']}]
        self.assertEqual(journal.verify(present, facts['analysis'], facts['authorities'])[0], 'satisfied')

    def test_mutation_unadmitted_execution_and_authority_violations_fail(self):
        broad = self.authority(('workspace.read', 'fixture.effect'))
        predicates = [{'name': 'operation_classes_subset', 'allowed': ['workspace.read']}]
        facts = self.facts([self.admitted('t/1', 'fixture.effect', broad), self.observed('t/1')], broad)
        self.assertEqual(journal.verify(predicates, facts['analysis'], facts['authorities'])[0], 'failed')
        narrow = self.authority()
        synthetic = self.facts([self.admitted('t/1', 'workspace.read', narrow, fx.WORKSPACE), self.observed('t/2')], narrow)
        status, detail = journal.verify([{'name': 'admitted_before_observed'}], synthetic['analysis'], synthetic['authorities'])
        self.assertEqual(status, 'failed')
        self.assertIn('observed without admission', detail)
        outside = self.facts([self.admitted('t/1', 'fixture.effect', narrow)], narrow)
        self.assertIn('outside effective authority', outside['analysis']['problems'][0])
        elsewhere = self.facts([self.admitted('t/1', 'workspace.read', narrow, '/work/other')], narrow)
        self.assertEqual(journal.verify([{'name': 'workspace_subset'}], elsewhere['analysis'], elsewhere['authorities'])[0], 'failed')


class NoMutation(JournalFixtures, unittest.TestCase):
    """"No mutation" means no unauthorized TARGET_EFFECT; INTERNAL_EFFECT never counts."""
    def test_effect_scopes_of_the_kernel_classification(self):
        scopes = {name: journal.effect_scope(journal.operation_class(name)) for name in journal.OPERATION_CLASSES}
        self.assertEqual({n for n, s in scopes.items() if s == journal.INTERNAL_EFFECT},
                         {'artifact.write', 'artifact.read', 'human.request', 'text.stats'})
        self.assertEqual({n for n, s in scopes.items() if s == journal.TARGET_READ}, {'workspace.read', 'youtrack.read'})
        self.assertEqual({n for n, s in scopes.items() if s == journal.TARGET_EFFECT}, {'worker.run', 'fixture.effect'})
        for unreviewed in ('database.write', 'unclassified', 'workspace.write', 'workspace.exec'):
            self.assertEqual(journal.effect_scope(unreviewed), journal.TARGET_EFFECT)

    def test_internal_effects_and_reads_do_not_violate_no_mutation(self):
        authority = self.authority(('workspace.read', 'youtrack.read', 'artifact.write', 'artifact.read',
                                    'human.request', 'text.stats'))
        entries = []
        for n, capability in enumerate(('workspace.read', 'youtrack.read', 'artifact.write', 'artifact.read',
                                        'human.request', 'text.stats')):
            entries += [self.admitted(f't/{n}', capability, authority, fx.WORKSPACE if capability == 'workspace.read' else None),
                        self.observed(f't/{n}')]
        facts = self.facts(entries, authority)
        status, detail = journal.verify([{'name': 'no_target_effect'}], facts['analysis'], facts['authorities'])
        self.assertEqual(status, 'satisfied', detail)

    def test_target_effect_violates_no_mutation_unless_explicitly_allowed(self):
        authority = self.authority(('workspace.read', 'fixture.effect'))
        facts = self.facts([self.admitted('t/1', 'fixture.effect', authority), self.observed('t/1')], authority)
        self.assertEqual(journal.verify([{'name': 'no_target_effect'}], facts['analysis'], facts['authorities'])[0], 'failed')
        allowed = [{'name': 'no_target_effect', 'allowed': ['external.effect']}]
        self.assertEqual(journal.verify(allowed, facts['analysis'], facts['authorities'])[0], 'satisfied')
        denied = self.facts([{'phase': 'denied', 'decision_id': 't/1', 'capability': 'fixture.effect',
                              'operation_class': 'external.effect', 'provider': 'kernel', 'operation': 'fixture.effect',
                              'reason': 'denied', 'authority_ref': authority, 'contract_revision': 0}], authority)
        self.assertEqual(journal.verify([{'name': 'no_target_effect'}], denied['analysis'], denied['authorities'])[0],
                         'satisfied')  # prevention worked; nothing was admitted


class TerminalOrRemediable(unittest.TestCase):
    def test_only_failed_unwaivable_monotonic_invariants_are_terminal(self):
        invariant = fx.journal_criterion('no-mutation', [{'name': 'no_target_effect'}])
        user_journal = {**fx.journal_criterion('no-effects', [{'name': 'no_target_effect'}], invariant=False),
                        'provenance': {'source': 'user'}}
        default_journal = fx.journal_criterion('scope', [{'name': 'workspace_subset'}], invariant=False)
        tests_pass = user_digest('tests-pass')
        advisory_invariant = {**invariant, 'level': 'ADVISORY'}
        cases = [(invariant, 'failed', True), (invariant, 'pending', False), (invariant, 'unknown', False),
                 (user_journal, 'failed', False), (default_journal, 'failed', False), (tests_pass, 'failed', False),
                 ({**invariant, 'superseded_by': 'x'}, 'failed', False), (advisory_invariant, 'failed', False)]
        for criterion, status, expected in cases:
            with self.subTest(criterion=criterion['id'], status=status, level=criterion['level']):
                self.assertEqual(completion.terminal(criterion, {'status': status}), expected)


class RevisionZero(unittest.TestCase):
    def test_lowering_is_verbatim_ordered_and_one_to_one(self):
        request = fx.human_request(TASK, 'decide')
        items = [{'criterion': '  Exact bytes, including spacing — and Unicode ✓  ', 'evidence': {'artifact': 'answer', 'sha256': 'a' * 64}},
                 {'criterion': 'Exact bytes, including spacing — and Unicode ✓', 'evidence': {'artifact': 'answer', 'sha256': 'a' * 64}},
                 {'criterion': 'Human decided', 'evidence': {'artifact': 'decision', 'verifier': 'human_response', 'request': request}}]
        spec = validate_spec(message('TaskSpec', {'objective': 'o', 'completion': deepcopy(items)}))
        lowered = completion.lower_spec(spec, TASK)['criteria']
        self.assertEqual(len(lowered), len(items))  # near-duplicates are not merged
        for number, (item, criterion) in enumerate(zip(items, lowered), 1):
            self.assertEqual(criterion['id'], f'c{number}')
            self.assertEqual(criterion['requirement'].encode(), item['criterion'].encode())
            self.assertEqual(criterion['level'], 'REQUIRED')
            evidence = {k: v for k, v in criterion['verifier'].items() if k not in ('kind', 'version')}
            self.assertEqual(evidence, {k: v for k, v in item['evidence'].items() if k != 'verifier'})

    def test_envelope_cannot_summarize_merge_weaken_or_reinterpret_intake_criteria(self):
        spec = validate_spec(fx.investigation_spec())
        variants = {
            'summarized': lambda c: c[0].update(requirement='Source was read.'),
            'weakened': lambda c: c[0].update(level='ADVISORY'),
            'reinterpreted': lambda c: c[0].update(verifier={**c[0]['verifier'], 'sha256': 'f' * 64}),
            're-sourced': lambda c: c[0].update(provenance={'source': 'model'}),
            'superseded': lambda c: c[0].update(superseded_by='findings-cited'),
            'merged away': lambda c: c.pop(0),
        }
        for name, change in variants.items():
            contract = fx.investigation_contract(TASK)
            change(contract['payload']['criteria'])
            with self.subTest(name), self.assertRaises(ValueError):
                completion.accept_contract(spec, None, contract, TASK, False)


class Citation(Store, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.content_ref = self.store.put(TASK, fx.SOURCE.encode())
        request_ref = self.store.put_json(TASK, {'request': 'r'})
        self.receipt_ref = self.store.put_json(TASK, legacy_receipt(
            TASK, request_ref, {'operation_id': TASK + '/1', 'workspace': fx.WORKSPACE, 'path': fx.PATH},
            self.content_ref, fx.SOURCE))
        self.verifier = {'kind': 'evidence_citation', 'version': 1, 'artifact': 'findings', 'schema': 'InvestigationFindings@1',
                         'predicates': [{'name': 'every_claim_cited'}, {'name': 'quotes_match_receipts'},
                                        {'name': 'min_cited_receipts', 'operation': 'read_file', 'count': 1,
                                         'path_prefix': 'service/'},
                                        {'name': 'conclusion_status_present'}, {'name': 'unresolved_requires_uncertainty'}]}

    def verify(self, value, receipts=None):
        state = {'task_id': TASK, 'artifacts': {'findings': self.store.put(TASK, json.dumps(value).encode())}}
        return citation.verify(self.verifier, state, self.store, {self.receipt_ref} if receipts is None else receipts)

    def test_verified_quote_passes_and_fabrications_fail(self):
        status, detail, refs = self.verify(fx.findings(self.receipt_ref))
        self.assertEqual(status, 'satisfied', detail)
        self.assertIn(self.receipt_ref, refs)
        cases = {
            'fabricated quote': fx.findings(self.receipt_ref, quote='return Response.serverError();'),
            'right quote wrong lines': fx.findings(self.receipt_ref, lines=(3, 4)),
            'lines outside receipt': fx.findings(self.receipt_ref, lines=(40, 41)),
            'path mismatch': fx.findings(self.receipt_ref, path='service/Other.java'),
            'unresolved without uncertainty': fx.findings(self.receipt_ref, status='unresolved'),
            'bad schema': message('InvestigationFindings', {'claims': []}),
        }
        for name, value in cases.items():
            with self.subTest(name):
                self.assertEqual(self.verify(value)[0], 'failed')
        self.assertEqual(self.verify(fx.findings(self.receipt_ref, status='unresolved',
                                                 uncertainties=['Mapping to 500 not observed.']))[0], 'satisfied')

    def test_citing_unadmitted_receipts_fails(self):
        self.assertEqual(self.verify(fx.findings(self.receipt_ref), receipts=set())[0], 'failed')
        self.assertEqual(citation.verify(self.verifier, {'task_id': TASK, 'artifacts': {}}, self.store, set())[0], 'pending')


class SemanticStatus(unittest.TestCase):
    def result(self, verdict, confidence):
        return message('SemanticReviewResult', {'verdict': verdict, 'confidence': confidence, 'rationale': 'r'})

    def test_semantic_mapping_never_invents_pass(self):
        unknown = fx.semantic_criterion()['verifier']
        escalate = fx.semantic_criterion(on_low='request_human', artifact='review',
                                         request=fx.human_request(TASK, 'review'))['verifier']
        passed = {'findings-cited': 'satisfied'}
        cases = [
            (unknown, self.result('satisfied', 'high'), passed, None, 'satisfied'),
            (unknown, self.result('unsatisfied', 'high'), passed, None, 'failed'),
            (unknown, self.result('satisfied', 'low'), passed, None, 'unknown'),
            (unknown, self.result('request_human', 'high'), passed, None, 'unknown'),
            (escalate, self.result('satisfied', 'low'), passed, ('pending', 'missing'), 'waiting_human'),
            (escalate, self.result('satisfied', 'low'), passed, ('satisfied', 'accepted'), 'satisfied'),
            (unknown, message('SemanticReviewFailure', {'reason': 'No semantic reviewer is deployed'}), passed, None, 'unknown'),
            (unknown, self.result('satisfied', 'high'), {'findings-cited': 'pending'}, None, 'pending'),
            (unknown, None, passed, None, 'pending'),
        ]
        for verifier, retained, dependencies, human, expected in cases:
            with self.subTest(expected=expected, retained=retained):
                self.assertEqual(review.status(verifier, retained, dependencies, human)[0], expected)

    def test_semantic_cannot_override_deterministic_failure(self):
        status, detail, concern = review.status(fx.semantic_criterion()['verifier'], self.result('satisfied', 'high'),
                                                {'findings-cited': 'failed'}, None)
        self.assertEqual(status, 'unknown')
        self.assertIn('deterministic verdict stands', concern)

    def test_reviewer_output_is_validated_against_its_packet(self):
        packet = message('SemanticReviewRequest', {'task_id': TASK, 'criterion_id': 'cause-supported',
            'contract_revision': 0, 'evidence_digest': 'sha256:' + 'd' * 64, 'subject': 's', 'question': 'q',
            'deterministic': [], 'evidence': [{'name': 'findings', 'ref': ref(TASK, 'f'), 'content': '{}', 'truncated': False}]})
        good = message('SemanticReviewResult', {**{k: packet['payload'][k] for k in ('task_id', 'criterion_id',
            'contract_revision', 'evidence_digest')}, 'verdict': 'satisfied', 'confidence': 'high',
            'rationale': 'Supported.', 'evidence_refs': [ref(TASK, 'f')]})
        self.assertEqual(review.call(lambda p: good, packet), good)
        foreign = deepcopy(good)
        foreign['payload']['evidence_refs'] = [ref(TASK, 'elsewhere')]
        for adapter in (lambda p: foreign, lambda p: {'verdict': 'PASS'}, lambda p: 1 / 0):
            self.assertEqual(review.call(adapter, packet)['kind'], 'SemanticReviewFailure')
        self.assertEqual(review.call(None, packet)['kind'], 'SemanticReviewFailure')


class Legality(Store, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.contract = completion.validate_contract(contract([user_digest()]), TASK, False)
        self.contract_ref = self.store.put_json(TASK, message('CompletionContract', self.contract))
        answer = self.store.put(TASK, b'GOOD')
        self.state = {'task_id': TASK, 'artifacts': {'answer': answer}, 'contract_ref': self.contract_ref,
                      'contract_revision': 0, 'journal_head': None, 'journal_length': 0, 'wait': None}

    def evaluation(self, state=None):
        return completion.evaluate_contract(self.contract, self.contract_ref, state or self.state, self.store)['payload']

    def test_fresh_satisfied_evaluation_is_legal_and_reproducible(self):
        first = self.evaluation()
        self.assertTrue(first['legality']['legal'], first['legality'])
        self.assertEqual(first, self.evaluation())
        self.assertEqual(self.store.put_json(TASK, first), self.store.put_json(TASK, self.evaluation()))

    def test_stale_revision_evidence_and_outstanding_human_wait_block(self):
        first = self.evaluation()
        amended = {**self.state, 'contract_revision': 1, 'contract_ref': ref(TASK, 'r1')}
        self.assertIn('current contract revision', completion.legality(self.contract, self.contract_ref, first, amended, self.store)['blockers'][0])
        moved = {**self.state, 'artifacts': {**self.state['artifacts'], 'extra': ref(TASK, 'x')}}
        self.assertIn('stale', completion.legality(self.contract, self.contract_ref, first, moved, self.store)['blockers'][0])
        waiting = {**self.state, 'wait': {'input_type': 'human_response', 'wait_id': 'accept'}}
        self.assertFalse(self.evaluation(waiting)['legality']['legal'])

    def test_required_statuses_and_unbound_block_but_advisory_does_not(self):
        missing = self.evaluation({**self.state, 'artifacts': {}})
        self.assertEqual((missing['outcome'], missing['legality']['legal']), ('unsatisfied', False))
        advisory = completion.validate_contract(contract([user_digest(), user_digest('extra', level='ADVISORY', sha='e' * 64)]), TASK, False)
        result = completion.evaluate_contract(advisory, self.contract_ref, self.state, self.store)['payload']
        self.assertEqual(result['criteria'][1]['status'], 'failed')
        self.assertIn('Advisory extra failed', result['concerns'][0])
        self.assertEqual(result['outcome'], 'satisfied')
        unbound = completion.validate_contract(contract([user_digest(), {**user_digest('later'), 'verifier': {'kind': 'unbound'}}]), TASK, False)
        result = completion.evaluate_contract(unbound, self.contract_ref, self.state, self.store)['payload']
        self.assertIn('REQUIRED later is unbound', result['legality']['blockers'])

    def test_corruption_is_unknown_not_pass(self):
        path = self.store.root / TASK / self.state['artifacts']['answer'].rsplit(':', 1)[1]
        path.write_bytes(b'tampered')
        result = self.evaluation()
        self.assertEqual((result['outcome'], result['criteria'][0]['status'], result['legality']['legal']),
                         ('unknown', 'unknown', False))

    def test_waiver_must_reference_a_retained_authorized_human_action(self):
        base = completion.validate_contract(contract([user_digest(), user_digest('extra', sha='e' * 64)]), TASK, False)
        base_ref = self.store.put_json(TASK, message('CompletionContract', base))
        request = fx.amendment(TASK, [{'op': 'waive', 'id': 'extra', 'reason': 'Out of scope now.'}])
        action = self.store.put_json(TASK, request)
        state = {**self.state, 'contract_ref': base_ref}
        actor, content = completion.validate_amendment_submission(request, TASK)
        amendment, updated = completion.apply_amendment(base, base_ref, actor, content, action, state, False)
        amendment_ref = self.store.put_json(TASK, message('CompletionContractAmendment', amendment))
        sealed = completion.seal(updated, amendment_ref, TASK, False)
        sealed_ref = self.store.put_json(TASK, message('CompletionContract', sealed))
        current = {**state, 'contract_ref': sealed_ref, 'contract_revision': 1}
        result = completion.evaluate_contract(sealed, sealed_ref, current, self.store)['payload']
        self.assertTrue(result['legality']['legal'], result['legality'])
        self.assertEqual(result['criteria'][1]['status'], 'waived')
        self.assertIn('waived, not satisfied', result['concerns'][0])
        forged = deepcopy(sealed)
        forged['criteria'][1]['waiver']['actor']['ref'] = ref(TASK, 'never-retained')
        result = completion.evaluate_contract(forged, sealed_ref, current, self.store)['payload']
        self.assertFalse(result['legality']['legal'])
        self.assertIn('retained human action', result['legality']['blockers'][0])
        reattributed = deepcopy(sealed)  # the record claims operator; the retained action says user
        reattributed['criteria'][1]['waiver']['actor'].update(binding='operator-console')
        result = completion.evaluate_contract(reattributed, sealed_ref, current, self.store)['payload']
        self.assertFalse(result['legality']['legal'])
        self.assertIn('retained human action', result['legality']['blockers'][0])


class V0Parity(Store, unittest.TestCase):
    def test_v1_projection_keeps_existing_verdicts(self):
        request = fx.human_request(TASK, 'decide', ('YES', 'NO'))
        spec = validate_spec(message('TaskSpec', {'objective': 'o', 'completion': [
            {'criterion': 'Exact', 'evidence': {'artifact': 'answer', 'sha256': hashlib.sha256(b'GOOD').hexdigest()}},
            {'criterion': 'Decided', 'evidence': {'artifact': 'decision', 'verifier': 'human_response', 'request': request}}]}))
        good, wrong = self.store.put(TASK, b'GOOD'), self.store.put(TASK, b'BAD')
        response = self.store.put_json(TASK, fx.human_response(TASK, request, 'NO'))
        cases = [
            ({}, {}, 'unsatisfied', ['unsatisfied', 'unsatisfied']),
            ({'answer': wrong}, {}, 'unsatisfied', ['unsatisfied', 'unsatisfied']),
            ({'answer': good, 'decision': response}, {}, 'unknown', ['satisfied', 'unknown']),
            ({'answer': good, 'decision': response}, {'decide': response}, 'satisfied', ['satisfied', 'satisfied']),
        ]
        for artifacts, responses, overall, per in cases:
            with self.subTest(artifacts=artifacts, responses=responses):
                result = evaluate(spec, {'task_id': TASK, 'artifacts': artifacts, 'human_responses': responses}, self.store)
                self.assertEqual(result['version'], 1)
                self.assertEqual(result['payload']['outcome'], overall)
                self.assertEqual([c['outcome'] for c in result['payload']['criteria']], per)


if __name__ == '__main__':
    unittest.main()
