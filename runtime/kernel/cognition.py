"""A replaceable, effect-free scripted cognitive adapter for Increment 1."""
from copy import deepcopy
from dataclasses import dataclass

from runtime.kernel.contracts import NextAction, message, unpack


@dataclass(frozen=True)
class ScriptedCognition:
    actions: list[NextAction]

    def __call__(self, packet: dict) -> dict:
        turn = unpack(packet, "CognitiveTurn")
        index = turn["iteration"] - 1
        if index >= len(self.actions):
            raise ValueError("Script exhausted")
        return message("CognitiveDecision", {
            "task_id": turn["task_id"], "task_revision": turn["task_revision"],
            "turn_id": turn["turn_id"], "next_action": deepcopy(self.actions[index]),
        })
