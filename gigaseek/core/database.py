"""
GIGASEEK Database Layer
SQLite with async support for storing OSINT data
"""

import aiosqlite
import sqlite3
import json
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
import orjson


@dataclass
class Target:
    """OSINT target"""
    id: Optional[int] = None
    type: str = ""  # username, email, phone, domain, etc.
    value: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Finding:
    """OSINT finding"""
    id: Optional[int] = None
    target_id: int = 0
    source: str = ""
    url: str = ""
    data_type: str = ""  # email, phone, social, etc.
    data_value: str = ""
    confidence: int = 50
    raw_data: Dict[str, Any] = field(default_factory=dict)
    discovered_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Scan:
    """Scan record"""
    id: Optional[int] = None
    target_id: int = 0
    module: str = ""
    status: str = "pending"  # pending, running, completed, failed
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    results_count: int = 0
    error: Optional[str] = None


class DatabaseManager:
    """
    Async SQLite database manager for GIGASEEK
    """
    
    def __init__(self, db_path: str = "gigaseek.db"):
        self.db_path = db_path
        self.db: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def connect(self):
        """Connect to database and initialize schema"""
        self.db = await aiosqlite.connect(self.db_path)
        self.db.row_factory = aiosqlite.Row
        await self._create_schema()
    
    async def close(self):
        """Close database connection"""
        if self.db:
            await self.db.close()
    
    async def _create_schema(self):
        """Create database schema"""
        async with self._lock:
            # Targets table
            await self.db.execute("""
                CREATE TABLE IF NOT EXISTS targets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    value TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    UNIQUE(type, value)
                )
            """)
            
            # Findings table
            await self.db.execute("""
                CREATE TABLE IF NOT EXISTS findings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_id INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    url TEXT,
                    data_type TEXT NOT NULL,
                    data_value TEXT NOT NULL,
                    confidence INTEGER DEFAULT 50,
                    raw_data TEXT DEFAULT '{}',
                    discovered_at TEXT NOT NULL,
                    FOREIGN KEY (target_id) REFERENCES targets (id)
                )
            """)
            
            # Scans table
            await self.db.execute("""
                CREATE TABLE IF NOT EXISTS scans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_id INTEGER NOT NULL,
                    module TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    started_at TEXT,
                    completed_at TEXT,
                    results_count INTEGER DEFAULT 0,
                    error TEXT,
                    FOREIGN KEY (target_id) REFERENCES targets (id)
                )
            """)
            
            # Crawled pages cache
            await self.db.execute("""
                CREATE TABLE IF NOT EXISTS crawled_pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    status INTEGER,
                    content_hash TEXT,
                    crawled_at TEXT NOT NULL
                )
            """)
            
            # Create indexes
            await self.db.execute("CREATE INDEX IF NOT EXISTS idx_findings_target ON findings(target_id)")
            await self.db.execute("CREATE INDEX IF NOT EXISTS idx_findings_type ON findings(data_type)")
            await self.db.execute("CREATE INDEX IF NOT EXISTS idx_findings_value ON findings(data_value)")
            await self.db.execute("CREATE INDEX IF NOT EXISTS idx_scans_target ON scans(target_id)")
            await self.db.execute("CREATE INDEX IF NOT EXISTS idx_crawled_url ON crawled_pages(url)")
            
            await self.db.commit()
    
    async def insert_target(self, target: Target) -> int:
        """Insert or get target, returns target ID"""
        async with self._lock:
            # Check if exists
            cursor = await self.db.execute(
                "SELECT id FROM targets WHERE type = ? AND value = ?",
                (target.type, target.value)
            )
            row = await cursor.fetchone()
            
            if row:
                return row["id"]
            
            # Insert new
            cursor = await self.db.execute(
                """INSERT INTO targets (type, value, created_at, metadata)
                   VALUES (?, ?, ?, ?)""",
                (target.type, target.value, target.created_at, json.dumps(target.metadata))
            )
            await self.db.commit()
            return cursor.lastrowid
    
    async def insert_finding(self, finding: Finding) -> int:
        """Insert finding, returns finding ID"""
        async with self._lock:
            cursor = await self.db.execute(
                """INSERT INTO findings 
                   (target_id, source, url, data_type, data_value, confidence, raw_data, discovered_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    finding.target_id, finding.source, finding.url,
                    finding.data_type, finding.data_value, finding.confidence,
                    json.dumps(finding.raw_data), finding.discovered_at
                )
            )
            await self.db.commit()
            return cursor.lastrowid
    
    async def insert_findings_bulk(self, findings: List[Finding]) -> int:
        """Insert multiple findings, returns count inserted"""
        if not findings:
            return 0
        
        async with self._lock:
            data = [
                (
                    f.target_id, f.source, f.url, f.data_type,
                    f.data_value, f.confidence, json.dumps(f.raw_data), f.discovered_at
                )
                for f in findings
            ]
            
            await self.db.executemany(
                """INSERT INTO findings 
                   (target_id, source, url, data_type, data_value, confidence, raw_data, discovered_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                data
            )
            await self.db.commit()
            return len(findings)
    
    async def start_scan(self, scan: Scan) -> int:
        """Start a new scan, returns scan ID"""
        async with self._lock:
            scan.started_at = datetime.now().isoformat()
            scan.status = "running"
            
            cursor = await self.db.execute(
                """INSERT INTO scans (target_id, module, status, started_at)
                   VALUES (?, ?, ?, ?)""",
                (scan.target_id, scan.module, scan.status, scan.started_at)
            )
            await self.db.commit()
            return cursor.lastrowid
    
    async def complete_scan(self, scan_id: int, results_count: int, error: Optional[str] = None):
        """Mark scan as completed"""
        async with self._lock:
            status = "failed" if error else "completed"
            completed_at = datetime.now().isoformat()
            
            await self.db.execute(
                """UPDATE scans 
                   SET status = ?, completed_at = ?, results_count = ?, error = ?
                   WHERE id = ?""",
                (status, completed_at, results_count, error, scan_id)
            )
            await self.db.commit()
    
    async def get_target_findings(self, target_id: int) -> List[Finding]:
        """Get all findings for a target"""
        cursor = await self.db.execute(
            "SELECT * FROM findings WHERE target_id = ? ORDER BY confidence DESC",
            (target_id,)
        )
        rows = await cursor.fetchall()
        
        findings = []
        for row in rows:
            findings.append(Finding(
                id=row["id"],
                target_id=row["target_id"],
                source=row["source"],
                url=row["url"],
                data_type=row["data_type"],
                data_value=row["data_value"],
                confidence=row["confidence"],
                raw_data=json.loads(row["raw_data"]),
                discovered_at=row["discovered_at"],
            ))
        
        return findings
    
    async def search_findings(
        self,
        data_type: Optional[str] = None,
        data_value: Optional[str] = None,
        min_confidence: int = 0,
        limit: int = 100,
    ) -> List[Finding]:
        """Search findings with filters"""
        query = "SELECT * FROM findings WHERE 1=1"
        params = []
        
        if data_type:
            query += " AND data_type = ?"
            params.append(data_type)
        
        if data_value:
            query += " AND data_value LIKE ?"
            params.append(f"%{data_value}%")
        
        if min_confidence > 0:
            query += " AND confidence >= ?"
            params.append(min_confidence)
        
        query += " ORDER BY confidence DESC LIMIT ?"
        params.append(limit)
        
        cursor = await self.db.execute(query, params)
        rows = await cursor.fetchall()
        
        findings = []
        for row in rows:
            findings.append(Finding(
                id=row["id"],
                target_id=row["target_id"],
                source=row["source"],
                url=row["url"],
                data_type=row["data_type"],
                data_value=row["data_value"],
                confidence=row["confidence"],
                raw_data=json.loads(row["raw_data"]),
                discovered_at=row["discovered_at"],
            ))
        
        return findings
    
    async def get_statistics(self) -> dict:
        """Get database statistics"""
        cursor = await self.db.execute("SELECT COUNT(*) as count FROM targets")
        targets = (await cursor.fetchone())["count"]
        
        cursor = await self.db.execute("SELECT COUNT(*) as count FROM findings")
        findings = (await cursor.fetchone())["count"]
        
        cursor = await self.db.execute("SELECT COUNT(*) as count FROM scans")
        scans = (await cursor.fetchone())["count"]
        
        cursor = await self.db.execute(
            "SELECT data_type, COUNT(*) as count FROM findings GROUP BY data_type ORDER BY count DESC"
        )
        findings_by_type = {row["data_type"]: row["count"] for row in await cursor.fetchall()}
        
        cursor = await self.db.execute(
            "SELECT status, COUNT(*) as count FROM scans GROUP BY status"
        )
        scans_by_status = {row["status"]: row["count"] for row in await cursor.fetchall()}
        
        return {
            "total_targets": targets,
            "total_findings": findings,
            "total_scans": scans,
            "findings_by_type": findings_by_type,
            "scans_by_status": scans_by_status,
        }
    
    async def export_findings(self, target_id: Optional[int] = None) -> List[dict]:
        """Export findings to JSON-serializable format"""
        if target_id:
            findings = await self.get_target_findings(target_id)
        else:
            findings = await self.search_findings(limit=10000)
        
        return [asdict(f) for f in findings]
