"""Model SQLAlchemy -- satu sumber kebenaran skema, dipakai sesi sync
(Celery/CLI) dan async (FastAPI) sekaligus. Lihat db/engine.py.
"""

from cti_core.db.models.article import (
    Article,
    ArticleCountry,
    ArticleIndustry,
    ArticleThreatActor,
    ArticleTTP,
)
from cti_core.db.models.auth import AuditLogEntry, Client, ClientCountry, Role, User, UserClient
from cti_core.db.models.cve import (
    CveAffected,
    CveFalsePositive,
    CvePoc,
    CveReference,
    CveTicket,
    CveTicketItem,
    CveTracker,
)
from cti_core.db.models.ioc import IOC, IOCFeedback, IOCSource, IOCTag, IOCThreatActor
from cti_core.db.models.ioc_reference import IocAllowlistEntry, ThreatFeedEntry
from cti_core.db.models.malware_trend import MalwareTrend
from cti_core.db.models.package import (
    MonitoredPackage,
    PackageDepEdge,
    PackageVuln,
    PackageVulnAlias,
)
from cti_core.db.models.ransomware import RansomwareVictim
from cti_core.db.models.scraper import ScraperConfig, ScraperItem, ScraperRun, ScraperSeen
from cti_core.db.models.techstack import TechStackEntry
from cti_core.db.models.threat_reference import MonitoredPerson, ThreatActorGroup
from cti_core.db.models.tweet import MonitoredAccount, Tweet

__all__ = [
    "IOC",
    "Article",
    "ArticleCountry",
    "ArticleIndustry",
    "ArticleTTP",
    "ArticleThreatActor",
    "AuditLogEntry",
    "Client",
    "ClientCountry",
    "CveAffected",
    "CveFalsePositive",
    "CvePoc",
    "CveReference",
    "CveTicket",
    "CveTicketItem",
    "CveTracker",
    "IOCFeedback",
    "IOCSource",
    "IOCTag",
    "IOCThreatActor",
    "IocAllowlistEntry",
    "MalwareTrend",
    "MonitoredAccount",
    "MonitoredPackage",
    "MonitoredPerson",
    "PackageDepEdge",
    "PackageVuln",
    "PackageVulnAlias",
    "RansomwareVictim",
    "Role",
    "ScraperConfig",
    "ScraperItem",
    "ScraperRun",
    "ScraperSeen",
    "TechStackEntry",
    "ThreatActorGroup",
    "ThreatFeedEntry",
    "Tweet",
    "User",
    "UserClient",
]
