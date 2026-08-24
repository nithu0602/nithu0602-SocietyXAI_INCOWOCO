"""Core research metrics operating on RunTrace data.

All functions are pure, deterministic, and never mutate the input trace.
"""
from __future__ import annotations

from collections import Counter
from itertools import combinations

from societyxai.traces.schema import RunTrace


def consensus_score(trace: RunTrace) -> float:
    """Return a consensus score in [0.0, 1.0] based on final agent positions.

    Definition
    ----------
    Let *d* be the number of **distinct** ``belief.position`` values among
    the final-round ``AgentTrace`` entries, and *n* the number of those
    entries.

    * When *n* <= 1 (zero or one agent) the score is **1.0** by convention.
    * Otherwise::

        score = 1.0 - (d - 1) / (n - 1)

    This yields:

    * **1.0** when every agent holds the same position (d == 1).
    * **0.0** when every agent holds a unique position (d == n).
    * Linear interpolation for values in between.

    Returns 1.0 when the trace contains no agent traces (empty run).
    """
    final = _final_positions(trace)
    n = len(final)
    if n <= 1:
        return 1.0
    d = len(set(final))
    return 1.0 - (d - 1) / (n - 1)


def belief_divergence(trace: RunTrace) -> float:
    """Return the fraction of agent pairs whose final positions differ.

    Definition
    ----------
    Let *n* be the number of final-round ``AgentTrace`` entries and let
    *k* be the count of unordered pairs ``(i, j)`` where the two agents
    hold **different** ``belief.position`` values::

        divergence = k / C(n, 2)

    where ``C(n, 2) = n * (n - 1) / 2``.

    * **0.0** when all agents agree.
    * **1.0** when every pair disagrees (all positions distinct).
    * When *n* <= 1 there are no pairs, so **0.0** is returned.

    Returns 0.0 when the trace contains no agent traces (empty run).
    """
    final = _final_positions(trace)
    n = len(final)
    if n <= 1:
        return 0.0
    total_pairs = n * (n - 1) // 2
    disagreeing = sum(
        1 for a, b in combinations(final, 2) if a != b
    )
    return disagreeing / total_pairs


def convergence_round(trace: RunTrace) -> int:
    """Return the earliest round where all agents share the same position.

    The function groups ``AgentTrace`` entries by round and checks whether
    every agent active in that round holds the same ``belief.position``.

    * Returns the **1-based round number** of the first such round.
    * Returns **-1** if no round achieves full agreement.

    An empty trace (no agent traces) returns -1.
    """
    if not trace.agent_traces:
        return -1

    rounds: dict[int, list[str]] = {}
    for at in trace.agent_traces:
        rounds.setdefault(at.round, []).append(at.belief.position)

    for r in sorted(rounds):
        if len(set(rounds[r])) == 1:
            return r
    return -1


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _final_positions(trace: RunTrace) -> list[str]:
    """Extract the last ``belief.position`` for each distinct agent.

    Agents are identified by ``agent_id``.  If an agent appears in
    multiple ``AgentTrace`` entries the **last** entry (by list order)
    is used, which corresponds to the most recent round.
    """
    last_by_agent: dict[str, str] = {}
    for at in trace.agent_traces:
        last_by_agent[at.agent_id] = at.belief.position
    return list(last_by_agent.values())
