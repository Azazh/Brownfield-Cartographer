from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class ModuleNode(BaseModel):
    """Represents a source file/module."""
    path: str
    language: str  # 'python', 'sql', 'yaml', etc.
    purpose_statement: Optional[str] = None
    domain_cluster: Optional[str] = None
    complexity_score: Optional[float] = None
    change_velocity_30d: Optional[int] = None  # number of commits in last 30 days
    is_dead_code_candidate: bool = False
    last_modified: Optional[datetime] = None

    # Additional fields from Surveyor
    imports: List[str] = Field(default_factory=list)
    public_functions: List[str] = Field(default_factory=list)
    classes: List[str] = Field(default_factory=list)
    class_inheritance: Dict[str, List[str]] = Field(default_factory=dict)

class DatasetNode(BaseModel):
    """Represents a data set (table, file, stream)."""
    name: str
    storage_type: str  # 'table', 'file', 'stream', 'api'
    schema_snapshot: Optional[str] = None
    freshness_sla: Optional[str] = None
    owner: Optional[str] = None
    is_source_of_truth: bool = False

class FunctionNode(BaseModel):
    """Represents a function or method."""
    qualified_name: str
    parent_module: str   # file path
    signature: Optional[str] = None
    purpose_statement: Optional[str] = None
    call_count_within_repo: int = 0
    is_public_api: bool = False

class TransformationNode(BaseModel):
    """Represents a data transformation (SQL query, Python operation)."""
    source_datasets: List[str] = Field(default_factory=list)
    target_datasets: List[str] = Field(default_factory=list)
    transformation_type: str  # 'sql', 'pandas', 'spark', 'dbt', etc.
    source_file: str
    line_range: Optional[str] = None
    sql_query_if_applicable: Optional[str] = None

# Union type for any node (used in graph)
Node = ModuleNode | DatasetNode | FunctionNode | TransformationNode