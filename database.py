"""
Database management for Tunisian Proverbs
SQLite for metadata + ChromaDB for embeddings
"""

import sqlite3
import json
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime
import logging
import base64
from io import BytesIO

logger = logging.getLogger(__name__)


class ProverbDatabase:
    """SQLite database for proverbs and generated content"""

    def __init__(self, db_path: str = "data/proverbs.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Proverbs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS proverbs (
                id TEXT PRIMARY KEY,
                tunisan_proverb TEXT NOT NULL,
                context TEXT,
                proverb_arabic_explaination TEXT,
                image_path_1 TEXT,
                image_path_2 TEXT,
                image_path_3 TEXT,
                image_path_4 TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Generated content table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS generated_content (
                id TEXT PRIMARY KEY,
                proverb_id TEXT NOT NULL,
                interpretation_json TEXT,
                scene_json TEXT,
                generated_prompt TEXT,
                image_path TEXT,
                clip_score REAL,
                retry_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(proverb_id) REFERENCES proverbs(id)
            )
        """)

        # User queries table (for analytics)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                matched_proverb_id TEXT,
                generated_image_id TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")

    def load_proverbs_from_json(self, json_path: str):
        """Load proverbs from JSON file into database"""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                proverbs = json.load(f)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            for idx, proverb in enumerate(proverbs):
                proverb_id = f"proverb_{idx}"
                cursor.execute("""
                    INSERT OR REPLACE INTO proverbs 
                    (id, tunisan_proverb, context, proverb_arabic_explaination,
                     image_path_1, image_path_2, image_path_3, image_path_4)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    proverb_id,
                    proverb.get("tunisan_proverb", ""),
                    proverb.get("context", ""),
                    proverb.get("proverb_arabic_explaination", ""),
                    proverb.get("image_path_1", ""),
                    proverb.get("image_path_2", ""),
                    proverb.get("image_path_3", ""),
                    proverb.get("image_path_4", ""),
                ))

            conn.commit()
            conn.close()
            logger.info(f"Loaded {len(proverbs)} proverbs from {json_path}")
        except Exception as e:
            logger.error(f"Error loading proverbs: {e}")
            raise

    def get_proverb(self, proverb_id: str) -> Optional[Dict]:
        """Get proverb by ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM proverbs WHERE id = ?", (proverb_id,))
        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def get_all_proverbs(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Get all proverbs with pagination"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM proverbs LIMIT ? OFFSET ?",
            (limit, offset)
        )
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def search_proverbs(self, query: str, limit: int = 10) -> List[Dict]:
        """Search proverbs by text"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        search_term = f"%{query}%"
        cursor.execute(
            """
            SELECT * FROM proverbs 
            WHERE tunisan_proverb LIKE ? OR proverb_arabic_explaination LIKE ?
            LIMIT ?
            """,
            (search_term, search_term, limit)
        )
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def save_generated_content(self, content_id: str, proverb_id: str, 
                              interpretation: Dict, scene: Dict, 
                              prompt: str, image_path: str, clip_score: float = 0.0):
        """Save generated content"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO generated_content
            (id, proverb_id, interpretation_json, scene_json, generated_prompt, image_path, clip_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            content_id,
            proverb_id,
            json.dumps(interpretation),
            json.dumps(scene),
            prompt,
            image_path,
            clip_score
        ))

        conn.commit()
        conn.close()
        logger.info(f"Saved generated content: {content_id}")

    def get_generated_content(self, content_id: str) -> Optional[Dict]:
        """Get generated content by ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM generated_content WHERE id = ?", (content_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            result = dict(row)
            result['interpretation_json'] = json.loads(result['interpretation_json'])
            result['scene_json'] = json.loads(result['scene_json'])
            return result
        return None

    def log_query(self, query: str, matched_proverb_id: Optional[str] = None, 
                 generated_image_id: Optional[str] = None):
        """Log user query for analytics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO user_queries (query, matched_proverb_id, generated_image_id)
            VALUES (?, ?, ?)
        """, (query, matched_proverb_id, generated_image_id))

        conn.commit()
        conn.close()

    def count_proverbs(self) -> int:
        """Get total count of proverbs"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM proverbs")
        count = cursor.fetchone()[0]
        conn.close()

        return count

    def get_generated_for_proverb(self, proverb_id: str) -> Optional[Dict]:
        """Get generated content for a proverb"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM generated_content WHERE proverb_id = ? ORDER BY created_at DESC LIMIT 1",
            (proverb_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            result = dict(row)
            try:
                result['interpretation_json'] = json.loads(result['interpretation_json'])
                result['scene_json'] = json.loads(result['scene_json'])
            except:
                pass
            return result
        return None
