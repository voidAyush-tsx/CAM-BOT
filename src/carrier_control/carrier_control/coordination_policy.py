"""Pure coordination policy; carrier and local-motion adapters are separate."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CoordinationDecision:
    decision: str
    reason: str
    attempts: int


class CoordinationPolicy:
    """One carrier request per trial/step; recheck after movement is mandatory."""

    def __init__(self, max_attempts=1):
        if max_attempts != 1:
            raise ValueError("prototype permits exactly one reposition attempt")
        self.max_attempts = max_attempts
        self.issued = set()

    def reset(self):
        self.issued.clear()

    def choose(self, command_id, target_xyz_m, workpiece_state,
               world_from_base, reachability, candidate_station=None):
        if not command_id or not workpiece_state or target_xyz_m is None:
            return CoordinationDecision("ERROR", "INVALID_COMMAND", 0)
        if world_from_base is None or reachability.status == "UNKNOWN":
            return CoordinationDecision("ERROR", reachability.reason, 0)
        attempts = int(command_id in self.issued)
        if reachability.status == "REACHABLE":
            return CoordinationDecision("LOCAL_MANIPULATION",
                                        "CURRENT_TF_WITHIN_PROXY", attempts)
        if reachability.status != "UNREACHABLE":
            return CoordinationDecision("ERROR", "INVALID_REACHABILITY", attempts)
        if attempts >= self.max_attempts:
            return CoordinationDecision("UNREACHABLE", "RECHECK_STILL_UNREACHABLE",
                                        attempts)
        if candidate_station is None:
            return CoordinationDecision("UNREACHABLE", "NO_CARRIER_CANDIDATE", attempts)
        self.issued.add(command_id)
        return CoordinationDecision("CARRIER_REPOSITION",
                                    "CURRENT_TF_OUTSIDE_PROXY", attempts + 1)
