"""Deterministic influence tracking for SocietyXAI runs.

All functions are pure, deterministic, and never mutate the input trace.
"""
from __future__ import annotations

from collections import defaultdict

from societyxai.traces.schema import RunTrace


def influence_matrix(trace: RunTrace) -> dict[str, dict[str, int]]:
    """Return a nested dict counting how often each source influenced each target.

    Definition
    ----------
    Agent **A** is considered to have influenced agent **B** at a turn if:

    1. A's message is in B's ``received_message_ids`` for that turn (the
       message was *visible* to B), **and**
    2. B's ``belief.position`` for that turn **differs** from B's previous
       belief position (the position at B's immediately preceding turn), **or**
       B had no previous belief (first turn).

    The function iterates over ``AgentTrace`` entries sorted by
    ``(round, turn_index)``.  For each target turn it looks up every
    visible message in ``received_message_ids``, identifies the source
    agent from the ``MessageTrace`` list, and records the influence if
    the belief-position condition is met.

    Returns
    -------
    ``{source_id: {target_id: count}}`` where *count* is the number of
    turns in which source influenced target.  If no influence is found
    the dict is empty.  Both source and target keys are agent IDs
    (strings).
    """
    if not trace.agent_traces:
        return {}

    # Build a lookup: message_id -> source agent_id
    msg_to_source: dict[str, str] = {}
    for mt in trace.message_traces:
        msg_to_source[mt.message_id] = mt.agent_id

    # Sort agent traces chronologically
    sorted_traces = sorted(trace.agent_traces, key=lambda a: (a.round, a.turn_index))

    # Track previous belief position per agent
    prev_position: dict[str, str | None] = {}

    # Accumulate influence counts: {source -> {target -> count}}
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for at in sorted_traces:
        target = at.agent_id
        current_pos = at.belief.position
        previous_pos = prev_position.get(target)

        # Belief changed or this is the first turn for this agent
        belief_changed = previous_pos is None or current_pos != previous_pos

        if belief_changed:
            # Collect unique source agents whose messages are visible this turn.
            # Each unique source is counted at most once per belief-change turn.
            sources_this_turn: set[str] = set()
            for mid in at.received_message_ids:
                source = msg_to_source.get(mid)
                if source is not None and source != target:
                    sources_this_turn.add(source)
            for source in sources_this_turn:
                counts[source][target] += 1

        prev_position[target] = current_pos

    # Convert inner defaultdicts to plain dicts
    return {src: dict(tgts) for src, tgts in counts.items()}
