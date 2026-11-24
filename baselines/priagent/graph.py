"""Loan Desk adapter of the local PriAgent regulatory_graph v2."""
from langgraph.graph import END, START, StateGraph
from regulatory import (ObligationAnalysis, LocusAnalysis, ProgramVerification,
                        RegulatoryChallenge, RegulatoryDecision, materialize_decision, check_loci)

def build_graph(agents):
    def policy(state):
        return {"obligation": agents.call("policy_scan", ObligationAnalysis, {}).model_dump()}

    def locate(state):
        result = agents.call("locus_finder", LocusAnalysis, {"obligation": state["obligation"]})
        return {"loci": result.model_dump(), "locus_errors": check_loci(agents.case, result)}

    def verify_controls(state):
        return {"verification": agents.call("control_verifier", ProgramVerification, state).model_dump()}

    def challenge(state):
        return {"challenge": agents.call("counterexample_review", RegulatoryChallenge, state).model_dump()}

    def adjudicate(state):
        return {"decision": agents.call("regulatory_arbiter", RegulatoryDecision, state).model_dump()}

    def finalize(state):
        try:
            answer, notes = materialize_decision(agents.case, RegulatoryDecision.model_validate(state["decision"]))
        except ValueError as exc:
            return {"validation": {"validation_status": "INVALID_ANSWER", "errors": [{"code": "ANCHOR_ERROR", "message": str(exc)}]}}
        return {"answer": answer, "materialization_notes": notes,
                "validation": {"validation_status": "VALID", "errors": []}}

    def repair_anchors(state):
        decision = agents.call("anchor_repair", RegulatoryDecision, {
            "decision": state["decision"], "errors": state["validation"]["errors"]})
        if decision.status != state["decision"]["status"]:
            raise ValueError("Anchor repair must not change regulatory status")
        return {"decision": decision.model_dump(), "repair_attempted": True}

    # Use a dict state: v2 adds independently recorded control and challenge facts.
    graph = StateGraph(dict)
    # dict state requires merging updates explicitly rather than losing prior keys.
    def merging(action):
        return lambda state: {**state, **action(state)}
    for name, action in [("policy", policy), ("locate", locate), ("verify_controls", verify_controls),
                         ("challenge", challenge), ("adjudicate", adjudicate), ("finalize", finalize),
                         ("repair_anchors", repair_anchors)]:
        graph.add_node(name, merging(action))
    graph.add_edge(START, "policy")
    graph.add_edge("policy", "locate")
    graph.add_edge("locate", "verify_controls")
    graph.add_edge("verify_controls", "challenge")
    graph.add_edge("challenge", "adjudicate")
    graph.add_edge("adjudicate", "finalize")
    graph.add_conditional_edges("finalize", lambda s: "repair_anchors" if s["validation"]["validation_status"] != "VALID" and not s.get("repair_attempted") else END)
    graph.add_edge("repair_anchors", "finalize")
    return graph.compile()
