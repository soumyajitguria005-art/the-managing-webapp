from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql
from app.db.base import Base
from app.modules.datasets import models as dataset_models  # noqa: F401
from app.modules.academic import models as academic_models  # noqa: F401
from app.modules.identity import models as identity_models  # noqa: F401
from app.modules.scheduling import models as scheduling_models  # noqa: F401
from app.modules.booking import models as booking_models  # noqa: F401
from app.modules.exams import models as exam_models  # noqa: F401
from app.modules.change_mgmt import models as change_models  # noqa: F401
from app.modules.approvals import models as approval_models  # noqa: F401
from app.modules.integration import models as integration_models  # noqa: F401

def test_current_orm_mapping_compiles_for_postgresql():
    assert len(Base.metadata.tables) >= 78
    for table in Base.metadata.sorted_tables:
        sql = str(CreateTable(table).compile(dialect=postgresql.dialect()))
        assert sql.startswith("\nCREATE TABLE")
