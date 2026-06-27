"""Consensus-related post-dispatch step mixins."""

import logging
from typing import Any

from .dispatch_steps_base import PostDispatchBase

logger = logging.getLogger(__name__)


class PostDispatchConsensusMixin(PostDispatchBase):
    """Provides consensus resolution and five-axis consensus helpers."""

    def _resolve_consensus(
        self, collection: Any, mode: str
    ) -> tuple[list[dict[str, Any]], Any]:
        """Resolve consensus and get compression info. Returns (consensus_records, compression_info)."""
        consensus_records: list[dict[str, Any]] = []
        conflicts_count = collection.get("conflicts_count", 0)
        if conflicts_count > 0 or mode == "consensus":
            resolutions = self.coordinator.resolve_conflicts()
            for rec in resolutions:
                self.metrics_service.safe_record(lambda m, o=rec.outcome.value: m.record_consensus_round(o))
                consensus_records.append(
                    {
                        "topic": rec.topic,
                        "outcome": rec.outcome.value,
                        "final_decision": rec.final_decision,
                        "votes_for": rec.votes_for,
                        "votes_against": rec.votes_against,
                        "votes_abstain": rec.votes_abstain,
                    }
                )

        compression_info = None
        if self.enable_compression and self.compressor:
            stats = self.coordinator.get_compression_stats()
            if stats:
                compression_info = stats

        return consensus_records, compression_info

    def _run_five_axis_consensus(
        self, _task: str, worker_results: list[dict[str, Any]], mode: str, exec_result: Any
    ) -> dict[str, Any] | None:
        """Run five-axis consensus review (consensus mode only)."""
        if mode != "consensus" or not exec_result.success:
            return None

        try:
            from .five_axis_consensus import FiveAxisConsensusEngine, ReviewAxis

            fa_engine = FiveAxisConsensusEngine()
            review = fa_engine.create_review("system", "dispatcher")
            for wr in worker_results:
                output_text = wr.get("output") or wr.get("error") or ""
                if output_text:
                    fa_engine.add_axis_vote(review, ReviewAxis.CORRECTNESS, 0.8, 0.7)
                    fa_engine.add_axis_vote(review, ReviewAxis.READABILITY, 0.8, 0.7)
                    fa_engine.add_axis_vote(review, ReviewAxis.ARCHITECTURE, 0.8, 0.7)
                    fa_engine.add_axis_vote(review, ReviewAxis.SECURITY, 0.7, 0.6)
                    fa_engine.add_axis_vote(review, ReviewAxis.PERFORMANCE, 0.7, 0.6)
                    break
            fa_result = fa_engine.compute_consensus([review])
            five_axis_result = {
                "verdict": fa_result.verdict,
                "overall_consensus": fa_result.overall_consensus,
                "axis_consensus": fa_result.axis_consensus,
                "action_items": fa_result.action_items,
            }
            if self.usage_tracker:
                self.usage_tracker.tick("five_axis_consensus")
            return five_axis_result
        except (ImportError, AttributeError, ValueError, RuntimeError) as fa_err:
            logger.debug("Five-axis consensus failed: %s", fa_err)
            return None

    def _run_consensus_gate(
        self,
        task_description: str,
        worker_results: list[dict[str, Any]],
    ) -> Any | None:
        """Step 15.5: Pre-decision consensus gate (HC-2).

        Uses ConsensusGate to run ConsensusEngine as a *pre-decision*
        check before result assembly.  This is not a post-hoc conflict
        resolver — it evaluates whether worker outputs collectively meet
        consensus before committing the final result.

        Returns ``None`` when the gate is unavailable (graceful
        degradation that never blocks dispatch).
        """
        try:
            from .consensus_gate import ConsensusGate

            # Use the dispatcher's consensus_engine if available
            engine = getattr(self.dispatcher, "consensus_engine", None)
            if engine is None:
                logger.debug("ConsensusGate skipped: no consensus_engine available")
                return None

            gate = ConsensusGate()
            result = gate.check(
                task_description=task_description,
                worker_results=worker_results,
                consensus_engine=engine,
            )
            if self.usage_tracker:
                self.usage_tracker.tick("consensus_gate")
            logger.info(
                "ConsensusGate: outcome=%s approved=%s needs_review=%s",
                result.outcome,
                result.approved,
                result.needs_review,
            )
            return result
        except (ImportError, AttributeError, ValueError, RuntimeError) as cg_err:
            logger.warning("ConsensusGate failed: %s", cg_err)
            return None
