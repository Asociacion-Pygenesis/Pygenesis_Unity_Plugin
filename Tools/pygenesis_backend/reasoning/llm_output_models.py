from pydantic import BaseModel, Field
from typing import List, Dict, Any

from models import DetectedIssue, ActionStep, ExecutionPolicy


class LLMAnalysisOutput(BaseModel):
    summary: str = ""
    issues: List[DetectedIssue] = Field(default_factory=list)
    plan: List[ActionStep] = Field(default_factory=list)
    execution_policy: ExecutionPolicy = Field(default_factory=ExecutionPolicy)
    metadata: Dict[str, Any] = Field(default_factory=dict)