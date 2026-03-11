from pydantic import BaseModel, Field
from typing import Optional

class ImportEdge(BaseModel):
    """Module imports another module."""
    source: str   # module path
    target: str   # module path
    weight: int = 1
    source_file: Optional[str] = None
    line_range: Optional[str] = None

class ProducesEdge(BaseModel):
    """Transformation produces a dataset."""
    source: str   # transformation node identifier
    target: str   # dataset name
    transformation_type: str
    source_file: str
    line_range: Optional[str] = None

class ConsumesEdge(BaseModel):
    """Transformation consumes a dataset."""
    source: str   # transformation node identifier
    target: str   # dataset name
    transformation_type: str
    source_file: str
    line_range: Optional[str] = None

class CallsEdge(BaseModel):
    """Function calls another function."""
    source: str   # qualified function name
    target: str   # qualified function name
    source_file: str
    line_range: Optional[str] = None

class ConfiguresEdge(BaseModel):
    """Configuration file defines/modifies a module or pipeline."""
    source: str   # config file path
    target: str   # module/pipeline identifier
    config_type: str  # 'yaml', 'env', etc.
    source_file: str

# Union type for any edge
Edge = ImportEdge | ProducesEdge | ConsumesEdge | CallsEdge | ConfiguresEdge