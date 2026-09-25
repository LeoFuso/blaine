"""Composition root for the Personal Agent services (bridge and personal_acp).

Both transports instantiate the same services over the same durable Conversation
store and Task control surface, so IntelliJ (ACP) and the desktop see identical
semantics. Only the bridge process runs the ResultDelivery loop.
"""
import json
import os
from functools import cached_property
from pathlib import Path

from runtime.kernel.conversation import ConversationService
from runtime.personal_agent import PersonalAgent, RestateBinding

INGRESS = os.environ.get('BLAINE_D2_INGRESS', 'http://127.0.0.1:48080')


class Services:
    """Composition root: wires the Personal Agent services for this process."""

    def __init__(self):
        self.data_dir = Path(os.environ.get('BLAINE_D2_DATA', '.local/d2'))
        path = os.environ.get('BLAINE_DEPLOYMENT_CONFIG')
        self.deployment = json.loads(Path(path).read_text()) if path else {}

    @cached_property
    def agent(self):
        return PersonalAgent(RestateBinding(INGRESS))

    @cached_property
    def store(self):
        return ConversationService(self.data_dir)

    @cached_property
    def model(self):
        from runtime.personal_conversation import ConversationModel
        cognition = self.deployment.get('cognition')
        if not cognition:
            raise ValueError('No local model is deployed for the Personal Agent')
        return ConversationModel(endpoint=cognition['endpoint'], model=cognition['model'])

    @cached_property
    def conversation(self):
        from runtime.personal_conversation import PersonalConversation
        return PersonalConversation(self.store, self.model, self.agent)

    @cached_property
    def projection(self):
        from runtime.personal_projection import ConversationProjection
        return ConversationProjection(self.store, self.agent)

    @cached_property
    def briefs(self):
        from runtime.personal_brief import BriefService, CodingPolicy
        return BriefService(self.store, self.model, self.agent, CodingPolicy(self.deployment))

    def delivery(self):
        from runtime.personal_brief import BriefService, CodingPolicy
        from runtime.personal_delivery import ResultDelivery, ResultInterpreter
        # Its own store connection: the delivery thread never shares a SQLite handle.
        store = ConversationService(self.data_dir)
        model = self.model if self.deployment.get('cognition') else None
        briefs = (BriefService(store, model, self.agent, CodingPolicy(self.deployment))
                  if self.deployment.get('coding_workspaces') else None)
        return ResultDelivery(store, self.agent, ResultInterpreter(model), briefs)
