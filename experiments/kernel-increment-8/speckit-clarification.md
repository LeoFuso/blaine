Spec Kit clarification guidance, adapted for a bounded cognitive turn.
Source: https://raw.githubusercontent.com/github/spec-kit/main/templates/commands/clarify.md

Examine the proposed feature for decisions that affect its behavior, data,
failure handling, or verifiable acceptance. Prioritize consequential uncertainty;
leave cosmetic preferences and ordinary implementation choices alone. Ask one
focused question at a time, with a small set of alternatives or a brief answer.
Avoid asking for information already supplied. Once the answer resolves the
blocking uncertainty, incorporate it into the specification and continue. Do not
force clarification when the requirements are already adequate.

Blaine binding: this excerpt supplies procedure guidance only. A needed external
answer uses the accepted HumanDecisionRequest: publish it through human.request,
then WAIT for human_response. The request carries the concise question.
HumanInputReceipt supplies the accepted answer; a verified HumanDecisionResolution
in later context preserves the current scoped resolution. All effects remain
capability requests, and COMPLETE still requires independent verification. This
does not install or execute Spec Kit's repository scripts, hooks, or phase engine.
