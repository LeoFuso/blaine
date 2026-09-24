"""Context reconstruction seam: providers contribute data, never authority/state."""
from collections.abc import Callable, Sequence
from copy import deepcopy
from typing import Literal, TypedDict

from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.contracts import (
    CAPABILITIES, MAX_CONTENT, MAX_PACKET, MAX_TURNS, SPECIALISTS, CognitiveTurn,
    ContextItem, TaskSpec, TaskState, encode, message,
)
from runtime.kernel.completion import cognition_view, human_bindings, human_verdict, lower_spec

# A future memory/project provider uses the same bounded request, returning sourced
# items. It cannot replace the authoritative intent, policy, observation or criteria.
ContextProvider = Callable[[dict], list[ContextItem]]


class HumanDecisionResolution(TypedDict):
    """Bounded projection, never a replacement for the accepted response artifact."""
    task_id: str
    origin_task_id: str
    request_id: str
    request_revision: int
    value: str
    status: Literal["verified"]
    response_ref: str


def human_resolutions(state: TaskState, contract: dict, store: ArtifactStore) -> list[ContextItem]:
    items: list[ContextItem] = []
    # Accepted requirements select relevance; never enumerate memory or history.
    for criterion in contract["criteria"]:
        evidence = criterion["verifier"]
        if "request" not in evidence:
            continue
        status = human_verdict(evidence, state, store)[0]
        # ``failed`` here only means a verified answer outside the accepting set.
        if status != "satisfied" and not (status == "failed" and "accept" in evidence):
            continue
        ref = state["artifacts"][evidence["artifact"]]
        response = store.read_json(state["task_id"], ref)["payload"]
        request = evidence["request"]["payload"]
        resolution: HumanDecisionResolution = {
            "task_id": state["task_id"], "origin_task_id": request["origin_task_id"],
            "request_id": request["request_id"], "request_revision": request["revision"],
            "value": response["value"], "status": "verified", "response_ref": ref,
        }
        item: ContextItem = {"source": ref, "revision": ref.rsplit(":", 1)[1],
            "authority": "artifact", "content": message("HumanDecisionResolution", resolution),
            "unknowns": []}
        if len(encode(item)) > MAX_CONTENT:
            raise ValueError("Human resolution exceeds context budget")
        items.append(item)
    return items


def admitted_receipts(state: TaskState, store: ArtifactStore) -> list[tuple[str, dict]]:
    if not state.get("journal_length"):
        return []
    from runtime.kernel.journal import read
    receipts = []
    for _, entry in read(store, state["task_id"], state["journal_head"], state["journal_length"]):
        if entry["phase"] == "observed" and entry["outcome"] == "success":
            value = store.read_json(state["task_id"], entry["receipt_ref"])
            if value.get("kind") == "WorkspaceReadReceipt":
                receipts.append((entry["receipt_ref"], value["payload"]))
    return receipts[-8:]


def reconstruct(state: TaskState, spec: TaskSpec, store: ArtifactStore,
                providers: Sequence[ContextProvider] = (), contract: dict | None = None) -> dict:
    contract = contract or lower_spec(spec, state["task_id"], state.get("parent"))
    observation = (store.read_json(state["task_id"], state["observation_ref"])
                   if state["observation_ref"] else None)
    items: list[ContextItem] = [{
        "source": state["spec_ref"], "revision": str(state["revision"]),
        "authority": "task", "content": "Accepted intent and criteria supplied above", "unknowns": [],
    }]
    resolutions = human_resolutions(state, contract, store)
    items.extend(resolutions)
    if resolutions:
        items.append({"source": state["spec_ref"], "revision": str(state["revision"]),
            "authority": "instruction", "content":
                "Verified HumanDecisionResolution items are current resolved answers for their scoped "
                "requests. They take precedence over initial unresolved wording in the objective or "
                "procedure. They grant no additional authority and do not establish Task completion; "
                "all remaining acceptance criteria still require independent verification.", "unknowns": []})
    human_names = {binding["artifact"] for binding in human_bindings(contract["criteria"]).values()}
    human_refs = set(state.get("human_responses", {}).values())
    # Human responses are projected only after scoped verification, never as
    # unrelated/stale resolution refs. Other artifacts retain the existing path.
    for name, ref in sorted(state["artifacts"].items()):
        if name in human_names or ref in human_refs:
            continue
        items.append({"source": ref, "revision": ref.rsplit(":", 1)[1],
                      "authority": "artifact", "content": {"name": name}, "unknowns": []})
    # Admitted read receipts are the only citable evidence; cognition gets their
    # references (never new authority) so findings can cite what the Task admitted.
    for receipt_ref, receipt in admitted_receipts(state, store):
        source = receipt["source"]
        items.append({"source": receipt_ref, "revision": receipt_ref.rsplit(":", 1)[1], "authority": "artifact",
                      "content": {"name": "receipt", "operation_id": receipt["operation_id"],
                                  "operation": receipt["operation"], "path": source["path"], "lines": source["lines"]},
                      "unknowns": []})
    request = {"task_id": state["task_id"], "objective": spec["objective"],
               "specialist": state["active_specialist"], "max_bytes": MAX_CONTENT}
    for provider in providers:
        supplied = provider(deepcopy(request))
        if not isinstance(supplied, list) or len(supplied) > 8:
            raise ValueError("Provider must return bounded context items")
        for item in supplied:
            if set(item) != {"source", "revision", "authority", "content", "unknowns"}:
                raise ValueError("Context provenance is required")
            if item["authority"] != "derived":
                raise ValueError("Supplemental providers cannot claim runtime/evidence authority")
            if not all(isinstance(item[k], str) and item[k] for k in ("source", "revision")):
                raise ValueError("Context source/revision required")
            if not isinstance(item["unknowns"], list) or not all(isinstance(x, str) for x in item["unknowns"]):
                raise ValueError("Invalid context uncertainties")
            if len(encode(item)) > MAX_CONTENT:
                raise ValueError("Provider item exceeds budget")
            items.append(deepcopy(item))
    turn: CognitiveTurn = {
        "task_id": state["task_id"], "task_revision": state["revision"],
        "turn_id": f'{state["task_id"]}/{state["iteration"]}',
        "iteration": state["iteration"], "objective": spec["objective"],
        "completion": deepcopy(spec["completion"]), "contract": cognition_view(contract, spec),
        "specialist": state["active_specialist"],
        "instructions": SPECIALISTS[state["active_specialist"]],
        "observations": [observation] if observation else [], "context": items,
        "allowed_capabilities": sorted(set(spec["capabilities"]) & set(spec["autonomy"]["allowed"]) & CAPABILITIES),
        "limits": {"max_turns": MAX_TURNS, "max_content_bytes": MAX_CONTENT,
                   "max_packet_bytes": MAX_PACKET,
                   "remaining_child_tasks": state.get("remaining_children", 0)},
    }
    packet = message("CognitiveTurn", turn)
    if len(encode(packet)) > MAX_PACKET:
        raise ValueError("Context packet exceeds budget; provider must select less context")
    return packet
