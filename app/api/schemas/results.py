from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import Field

from .common import APIModel, CountsSummary, UISectionItem


class GraphResultsResponse(APIModel):
    run_id: str
    scope: Optional[str] = None
    status: str
    graph_status: Optional[str] = None
    kb_index_status: Optional[str] = None
    executive_summary: Optional[Any] = None
    counts: CountsSummary
    hypotheses: List[UISectionItem] = Field(default_factory=list)
    selected_tests: List[UISectionItem] = Field(default_factory=list)
    findings: List[UISectionItem] = Field(default_factory=list)
    scores: List[UISectionItem] = Field(default_factory=list)
    explanations: List[UISectionItem] = Field(default_factory=list)
    second_level_analysis: List[UISectionItem] = Field(default_factory=list)
    comparison_insights: List[UISectionItem] = Field(default_factory=list)


class ReportRanking(APIModel):
    row_count: int = 0
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    top_k: Optional[int] = None


class ReportResponse(APIModel):
    run_id: str
    scope: Optional[str] = None
    status: str
    overall_status: Optional[str] = None
    summary: Dict[str, Any] = Field(default_factory=dict)
    ranking: ReportRanking = Field(default_factory=ReportRanking)
    test_runs: List[Dict[str, Any]] = Field(default_factory=list)
    artifact_paths: Dict[str, str] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
