"""Structural projection controls, not context quality or DLP evaluation."""
from dataclasses import asdict, replace, FrozenInstanceError
import hashlib
import unittest
from test_kernel_frontier import fixture, Provider
from runtime.kernel.frontier import authorize, invoke, DispatchBudget
from runtime.kernel.frontier_context import (ProjectedContext, ProjectionError, IdentityProjector,
    project_context, valid_projection)

RAW='organization=ORCHID; marker=RAW_SECRET_7319'
OUT='organization=FLOWER; marker=MASKED_7319'

class FixtureProjector:
    projector_id='synthetic-replacement-v1'
    def __init__(self): self.calls=0
    def project(self, resolved):
        self.calls+=1
        return resolved.replace('ORCHID','FLOWER').replace('RAW_SECRET_7319','MASKED_7319')

class ProjectionTests(unittest.TestCase):
    def test_visible_transform_exact_digest_and_adapter_input(self):
        a,p,kw=fixture(); projector=FixtureProjector()
        context=project_context('case',RAW,projector)
        self.assertEqual(projector.calls,1); self.assertEqual(context.content,OUT)
        a=replace(a,context_ref=context.ref); p['payload']['context_ref']=context.ref
        gate,r=authorize(p,a,DispatchBudget(),**(kw|{'context':context}))
        self.assertEqual(gate['outcome'],'allow')
        self.assertEqual(r.context_digest,hashlib.sha256(OUT.encode()).hexdigest())
        self.assertNotEqual(r.context_digest,hashlib.sha256(RAW.encode()).hexdigest())
        provider=Provider(); result=invoke(r,provider,guardrails=kw['guardrails'],authority=a)
        self.assertEqual(result['status'],'executed')
        self.assertIs(provider.calls[0].context,context)
        self.assertNotIn('RAW_SECRET_7319',str(asdict(provider.calls[0])))
        with self.assertRaises(FrozenInstanceError): context.content=RAW
        with self.assertRaises(TypeError): ProjectedContext()

    def test_authorization_rejects_raw_dict_wrong_task_and_raw_digest_grant(self):
        a,p,kw=fixture(); projected=project_context('case',RAW,FixtureProjector())
        for context in (RAW,asdict(projected),project_context('other',RAW,FixtureProjector())):
            gate,r=authorize(p,a,DispatchBudget(),**(kw|{'context':context}))
            self.assertEqual(gate['reason_category'],'context_not_projected'); self.assertIsNone(r)
        # Raw artifact authority cannot be used with the transformed projection.
        a=replace(a,context_ref='artifact://case/sha256:'+hashlib.sha256(RAW.encode()).hexdigest())
        p['payload']['context_ref']=a.context_ref
        self.assertEqual(authorize(p,a,DispatchBudget(),**(kw|{'context':projected}))[0]['reason_category'],'context_denied')

    def test_post_authorization_substitutions_never_reach_provider(self):
        a,p,kw=fixture(); _,r=authorize(p,a,DispatchBudget(),**kw)
        other=project_context('case',RAW,IdentityProjector()); provider=Provider()
        substitutions=[replace(r,context=RAW),replace(r,context=asdict(other)),
            replace(r,context=other),replace(r,context_digest=other.digest),
            replace(r,context=other,context_digest=other.digest,context_ref=other.ref),
            replace(r,authority_digest='0'*64)]
        for changed in substitutions:
            result=invoke(changed,provider,guardrails=kw['guardrails'],authority=a)
            self.assertFalse(result['provider_invoked']); self.assertEqual(result['reason_category'],'context_authorization_mismatch')
        self.assertEqual(provider.calls,[])

    def test_projection_failure_and_malformed_output_no_fallback(self):
        provider=Provider()
        class Broken:
            projector_id='broken-fixture'
            def project(self,resolved): raise RuntimeError(RAW)
        class Malformed:
            projector_id='malformed-fixture'
            def project(self,resolved): return {'raw':resolved}
        for projector in (Broken(),Malformed()):
            with self.assertRaises(ProjectionError) as error:
                context=project_context('case',RAW,projector)
                a,p,kw=fixture()
                _,r=authorize(p,a,DispatchBudget(),**(kw|{'context':context}))
                if r: invoke(r,provider,guardrails=kw['guardrails'],authority=a)
            self.assertNotIn(RAW,str(error.exception))
        self.assertEqual(provider.calls,[])

    def test_identity_and_fresh_projection_are_deterministic(self):
        a=project_context('case','public é\n',IdentityProjector())
        b=project_context('case','public é\n',IdentityProjector())
        self.assertEqual(a,b); self.assertIsNot(a,b)
        self.assertTrue(valid_projection(a,'case'))
        self.assertEqual(a.digest,hashlib.sha256('public é\n'.encode('utf-8')).hexdigest())
