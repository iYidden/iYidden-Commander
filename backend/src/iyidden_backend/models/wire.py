"""Wire-level pydantic models. Mirrors docs/protocol.md.

Discriminated unions on `type` make routing cheap and validation strict —
unknown types fail at parse time, not deep in a handler.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

# ---- Core domain ----------------------------------------------------------


class LaneCommit(BaseModel):
    sha: str
    message: str
    ts: datetime


class LaneTests(BaseModel):
    status: Literal["green", "yellow", "red", "unknown"] = "unknown"
    summary: str = ""


class Lane(BaseModel):
    id: str
    agent_id: str
    branch: str
    worktree_path: str
    last_commit: LaneCommit | None = None
    tests: LaneTests = Field(default_factory=LaneTests)
    claude_activity: str = ""
    health: Literal["green", "yellow", "red"] = "green"
    idle_since: datetime | None = None
    pending_question_id: str | None = None
    updated_at: datetime


class Question(BaseModel):
    id: str
    lane_id: str
    prompt: str = Field(max_length=400)
    options: list[str] = Field(min_length=2, max_length=6)
    created_at: datetime
    answered_at: datetime | None = None
    answered_choice_index: int | None = None


class EmergencyOption(BaseModel):
    key: str
    label: str
    description: str = ""


class EmergencySummary(BaseModel):
    lane_id: str | None = None
    summary_md: str
    options: list[EmergencyOption]


# ---- Git ops --------------------------------------------------------------

GitOp = Literal[
    "view_log",
    "view_diff",
    "merge_to_main",
    "revert_last_commit",
    "abort_lane",
    "switch_branch",
]


class GitOpRequest(BaseModel):
    lane_id: str
    op: GitOp
    args: dict = Field(default_factory=dict)


# ---- Envelopes ------------------------------------------------------------

_PROTOCOL_VERSION = 0


class _Envelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    v: int = _PROTOCOL_VERSION


# ---- Phone -> server ------------------------------------------------------


class PhoneSubscribe(_Envelope):
    type: Literal["subscribe"] = "subscribe"
    id: str | None = None


class PhoneAnswerQuestion(_Envelope):
    type: Literal["answer_question"] = "answer_question"
    id: str | None = None
    question_id: str
    choice_index: int = Field(ge=0)


class PhoneGitOp(_Envelope):
    type: Literal["git_op"] = "git_op"
    id: str | None = None
    lane_id: str
    op: GitOp
    args: dict = Field(default_factory=dict)


class PhoneRequestZalOverride(_Envelope):
    type: Literal["request_zal_override"] = "request_zal_override"
    id: str | None = None
    reason: Literal["friday", "secular_holiday", "chabad_holiday"]


class PhoneEmergencyAction(_Envelope):
    type: Literal["emergency_action"] = "emergency_action"
    id: str | None = None
    lane_id: str | None = None
    action: str
    pin: str = Field(min_length=6, max_length=6)


class PhoneRequestFreeformUnlock(_Envelope):
    type: Literal["request_freeform_unlock"] = "request_freeform_unlock"
    id: str | None = None
    lane_id: str
    minutes: int = Field(ge=1, le=60)
    pin: str = Field(min_length=6, max_length=6)


class PhonePing(_Envelope):
    type: Literal["ping"] = "ping"
    id: str | None = None


PhoneInbound = Annotated[
    Union[
        PhoneSubscribe,
        PhoneAnswerQuestion,
        PhoneGitOp,
        PhoneRequestZalOverride,
        PhoneEmergencyAction,
        PhoneRequestFreeformUnlock,
        PhonePing,
    ],
    Field(discriminator="type"),
]


# ---- Server -> phone ------------------------------------------------------


class SrvLaneSnapshot(_Envelope):
    type: Literal["lane_snapshot"] = "lane_snapshot"
    lanes: list[Lane]


class SrvLaneUpdate(_Envelope):
    type: Literal["lane_update"] = "lane_update"
    lane: Lane


class SrvLaneRemoved(_Envelope):
    type: Literal["lane_removed"] = "lane_removed"
    lane_id: str


class SrvQuestion(_Envelope):
    type: Literal["question"] = "question"
    question: Question


class SrvQuestionResolved(_Envelope):
    type: Literal["question_resolved"] = "question_resolved"
    question_id: str


class SrvEmergencySummary(_Envelope):
    type: Literal["emergency_summary"] = "emergency_summary"
    summary: EmergencySummary


class SrvZalOverrideResult(_Envelope):
    type: Literal["zal_override_result"] = "zal_override_result"
    granted: bool
    until: datetime | None = None
    reason: str = ""


class SrvFreeformUnlockResult(_Envelope):
    type: Literal["freeform_unlock_result"] = "freeform_unlock_result"
    granted: bool
    until: datetime | None = None
    session_id: str | None = None
    reason: str = ""


class SrvNotification(_Envelope):
    type: Literal["notification"] = "notification"
    title: str
    body: str
    lane_id: str | None = None
    severity: Literal["info", "warn", "error"] = "info"


class SrvAck(_Envelope):
    type: Literal["ack"] = "ack"
    ref_id: str | None = None


class SrvError(_Envelope):
    type: Literal["error"] = "error"
    code: int
    message: str
    ref_id: str | None = None


class SrvPong(_Envelope):
    type: Literal["pong"] = "pong"


PhoneOutbound = Annotated[
    Union[
        SrvLaneSnapshot,
        SrvLaneUpdate,
        SrvLaneRemoved,
        SrvQuestion,
        SrvQuestionResolved,
        SrvEmergencySummary,
        SrvZalOverrideResult,
        SrvFreeformUnlockResult,
        SrvNotification,
        SrvAck,
        SrvError,
        SrvPong,
    ],
    Field(discriminator="type"),
]


# ---- Agent -> server ------------------------------------------------------


class AgentRegister(_Envelope):
    type: Literal["register"] = "register"
    agent_id: str
    hostname: str
    lane_capacity: int = Field(ge=1, le=32)
    agent_version: str


class AgentLaneState(_Envelope):
    type: Literal["lane_state"] = "lane_state"
    lane: Lane


class AgentLaneRemoved(_Envelope):
    type: Literal["lane_removed"] = "lane_removed"
    lane_id: str


class AgentQuestionAsk(_Envelope):
    type: Literal["question_ask"] = "question_ask"
    lane_id: str
    prompt: str = Field(max_length=400)
    options: list[str] = Field(min_length=2, max_length=6)


class AgentGitOpResult(_Envelope):
    type: Literal["git_op_result"] = "git_op_result"
    op_id: str
    ok: bool
    output: str | None = None
    error: str | None = None


class AgentFreeformSessionEvent(_Envelope):
    type: Literal["freeform_session_event"] = "freeform_session_event"
    session_id: str
    kind: Literal["started", "output", "ended"]
    data: str | None = None


class AgentHeartbeat(_Envelope):
    type: Literal["heartbeat"] = "heartbeat"


AgentInbound = Annotated[
    Union[
        AgentRegister,
        AgentLaneState,
        AgentLaneRemoved,
        AgentQuestionAsk,
        AgentGitOpResult,
        AgentFreeformSessionEvent,
        AgentHeartbeat,
    ],
    Field(discriminator="type"),
]


# ---- Server -> agent ------------------------------------------------------


class SrvWelcome(_Envelope):
    type: Literal["welcome"] = "welcome"
    server_version: str
    max_lanes: int = 8


class SrvQuestionAnswered(_Envelope):
    type: Literal["question_answered"] = "question_answered"
    question_id: str
    choice_index: int


class SrvGitOpRequest(_Envelope):
    type: Literal["git_op_request"] = "git_op_request"
    op_id: str
    lane_id: str
    op: GitOp
    args: dict = Field(default_factory=dict)


class SrvEmergencyCommand(_Envelope):
    type: Literal["emergency_command"] = "emergency_command"
    lane_id: str | None = None
    action: Literal["kill_all", "pause_lane", "noop"]


class SrvStartFreeform(_Envelope):
    type: Literal["start_freeform_session"] = "start_freeform_session"
    session_id: str
    lane_id: str
    max_minutes: int = Field(ge=1, le=60)


class SrvStopFreeform(_Envelope):
    type: Literal["stop_freeform_session"] = "stop_freeform_session"
    session_id: str


AgentOutbound = Annotated[
    Union[
        SrvWelcome,
        SrvQuestionAnswered,
        SrvGitOpRequest,
        SrvEmergencyCommand,
        SrvStartFreeform,
        SrvStopFreeform,
    ],
    Field(discriminator="type"),
]
