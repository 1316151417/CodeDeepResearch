"""
Pipeline monitoring event types and event class.
Separated from base/types.py which handles ReAct streaming events.
"""
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import Any


class PipelineEventType(Enum):
    PIPELINE_START = "pipeline_start"
    PIPELINE_END = "pipeline_end"
    PIPELINE_ERROR = "pipeline_error"
    STAGE_START = "stage_start"
    STAGE_END = "stage_end"
    STAGE_ERROR = "stage_error"
    STAGE_SCAN_COMPLETE = "stage_scan_complete"
    STAGE_FILTER_COMPLETE = "stage_filter_complete"
    STAGE_DECOMPOSE_COMPLETE = "stage_decompose_complete"
    STAGE_SCORE_COMPLETE = "stage_score_complete"
    STAGE_RESEARCH_COMPLETE = "stage_research_complete"
    STAGE_AGGREGATE_COMPLETE = "stage_aggregate_complete"
    LLM_CALL = "llm_call"
    LLM_ERROR = "llm_error"
    HEARTBEAT = "heartbeat"


@dataclass
class PipelineEvent:
    event_id: str
    run_id: str
    type: PipelineEventType
    stage: str | None
    timestamp: str
    data: dict
    step: int = 1

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "run_id": self.run_id,
            "type": self.type.value,
            "stage": self.stage,
            "timestamp": self.timestamp,
            "data": self.data,
            "step": self.step,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PipelineEvent":
        d = dict(d)
        d["type"] = PipelineEventType(d["type"])
        return cls(**d)

    @staticmethod
    def new(
        run_id: str,
        event_type: PipelineEventType,
        stage: str | None,
        data: dict,
        step: int = 1,
    ) -> "PipelineEvent":
        return PipelineEvent(
            event_id=uuid.uuid4().hex[:12],
            run_id=run_id,
            type=event_type,
            stage=stage,
            timestamp=datetime.now().isoformat(),
            data=data,
            step=step,
        )
