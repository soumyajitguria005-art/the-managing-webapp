from app.db.base import Base
from app.modules.datasets import models as datasets_models
from app.modules.academic import models as academic_models
from app.modules.identity import models as identity_models
from app.modules.scheduling import models as scheduling_models
from app.modules.booking import models as booking_models
from app.modules.exams import models as exams_models
from app.modules.change_mgmt import models as change_mgmt_models
from app.modules.approvals import models as approvals_models
from app.modules.analytics import models as analytics_models
from app.modules.assistant import models as assistant_models
from app.modules.notifications import models as notifications_models
from app.modules.integration import models as integration_models

__all__ = ["Base"]
