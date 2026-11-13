"""Local OpenSkill v2 FTS5 discovery and reviewed prompt-bundle construction."""
import hashlib
import json
import os
import re
import sqlite3
import threading
from pathlib import Path


class OpenSkillsStore:
    def __init__(self, db_path, projects_db, catalog_path):
        self.db_path = Path(db_path)
        self.catalog_path = Path(catalog_path)
        self.projects_db = projects_db
        self.lock = threading.RLock()
        self.db_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(str(self.db_path), check_same_thread=False)
        os.chmod(self.db_path, 0o600)
        self.db.execute("CREATE TABLE IF NOT EXISTS manifests (skill_id TEXT PRIMARY KEY, body TEXT NOT NULL, deprecated INTEGER NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS store_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        fts_schema=self.db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='skills_fts'").fetchone()
        if fts_schema and "content=''" in fts_schema[0]:
            self.db.execute("DROP TABLE skills_fts")
            self.db.execute("DELETE FROM store_meta WHERE key='catalog_sha256'")
        self.db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS skills_fts USING fts5(skill_id UNINDEXED, title, summary, keywords, guild)")
        self.projects_db.execute("CREATE TABLE IF NOT EXISTS user_learned_rules (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL)")
        self.projects_db.commit()
        self._index_catalog()

    def _index_catalog(self):
        raw = self.catalog_path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        with self.lock:
            row = self.db.execute("SELECT value FROM store_meta WHERE key='catalog_sha256'").fetchone()
            if row and row[0] == digest:
                return
            artifact = json.loads(raw)
            if not isinstance(artifact, dict) or artifact.get("schema") != "openskill-v2" or not isinstance(artifact.get("manifests"), list):
                raise ValueError("Invalid OpenSkills v2 catalog")
            manifests = artifact["manifests"]
            self.db.execute("DELETE FROM skills_fts")
            self.db.execute("DELETE FROM manifests")
            for manifest in manifests:
                self._validate_manifest(manifest)
                header = manifest["header"]
                body = json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))
                self.db.execute(
                    "INSERT INTO manifests(skill_id,body,deprecated) VALUES(?,?,?)",
                    (header["skill_id"], body, int(manifest["deprecated"])),
                )
                self.db.execute(
                    "INSERT INTO skills_fts(skill_id,title,summary,keywords,guild) VALUES(?,?,?,?,?)",
                    (
                        header["skill_id"], header["branded_title"], header["summary_140"],
                        " ".join(header["trigger_keywords"]), header["guild"],
                    ),
                )
            self.db.execute("INSERT OR REPLACE INTO store_meta(key,value) VALUES('catalog_sha256',?)", (digest,))
            self.db.commit()

    @staticmethod
    def _validate_manifest(manifest):
        if not isinstance(manifest, dict) or not isinstance(manifest.get("header"), dict):
            raise ValueError("Invalid OpenSkill manifest")
        header = manifest["header"]
        required = {"skill_id", "branded_title", "guild", "summary_140", "trigger_keywords", "recommended_model_tier", "parallel_safe"}
        if set(header) != required or not isinstance(manifest.get("builder_instructions"), str):
            raise ValueError("Incomplete OpenSkill manifest")
        if not isinstance(manifest.get("challenger_rubric"), dict) or not isinstance(manifest.get("verification_contract"), dict):
            raise ValueError("Incomplete OpenSkill counter-rubric")
        if manifest.get("content_basis") not in {"source_prompt", "metadata_only"} or not isinstance(manifest.get("deprecated"), bool):
            raise ValueError("Invalid OpenSkill provenance")

    @staticmethod
    def _public(header, score=0.0, reason="Local catalog browse"):
        return {
            **header,
            "id": header["skill_id"],
            "name": header["branded_title"],
            "description": header["summary_140"],
            "tags": header["trigger_keywords"],
            "score": score,
            "reason": reason,
        }

    def search(self, query, guild="", limit=10, include_deprecated=False):
        if not isinstance(query, str) or len(query) > 5000:
            raise ValueError("query must be text within 5000 characters")
        if not isinstance(guild, str) or len(guild) > 100:
            raise ValueError("guild must be text within 100 characters")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20:
            raise ValueError("limit must be between 1 and 20")
        if not isinstance(include_deprecated, bool):
            raise ValueError("include_deprecated must be a boolean")
        query = query.strip()
        tokens = re.findall(r"\w+", query.lower(), re.UNICODE)[:16]
        with self.lock:
            if tokens:
                expression = " AND ".join('"' + token.replace('"', '""') + '"*' for token in tokens)
                sql = (
                    "SELECT m.body,bm25(skills_fts) AS rank FROM skills_fts "
                    "JOIN manifests m ON m.skill_id=skills_fts.skill_id "
                    "WHERE skills_fts MATCH ? "
                )
                params = [expression]
                if not include_deprecated:
                    sql += "AND m.deprecated=0 "
                if guild:
                    sql += "AND json_extract(m.body,'$.header.guild')=? "
                    params.append(guild)
                sql += "ORDER BY rank LIMIT ?"
                params.append(limit)
                rows = self.db.execute(sql, params).fetchall()
                return [self._public(json.loads(body)["header"], -rank, "Local FTS5 match: " + query) for body, rank in rows]
            sql = "SELECT body FROM manifests WHERE 1=1"
            params = []
            if not include_deprecated:
                sql += " AND deprecated=0"
            if guild:
                sql += " AND json_extract(body,'$.header.guild')=?"
                params.append(guild)
            sql += " ORDER BY json_extract(body,'$.header.branded_title') LIMIT ?"
            params.append(limit)
            return [self._public(json.loads(row[0])["header"]) for row in self.db.execute(sql, params).fetchall()]

    def manifest(self, skill_id):
        if not isinstance(skill_id, str) or len(skill_id) > 400:
            raise ValueError("Invalid skill_id")
        with self.lock:
            row = self.db.execute("SELECT body FROM manifests WHERE skill_id=? AND deprecated=0", (skill_id,)).fetchone()
        if not row:
            raise ValueError("Unknown selection")
        return json.loads(row[0])

    def learned_rules(self):
        row = self.projects_db.execute("SELECT body FROM user_learned_rules WHERE id=1").fetchone()
        if not row:
            return []
        try:
            rules = json.loads(row[0])
        except (ValueError, TypeError):
            return []
        return rules if isinstance(rules, list) else []

    def learn(self, rule):
        if not isinstance(rule, str) or not rule.strip() or len(rule) > 500:
            raise ValueError("rule must be nonempty text within 500 characters")
        rule = rule.strip()
        with self.lock:
            rules = self.learned_rules()
            if rule in rules:
                raise ValueError("Rule already exists")
            if len(rules) >= 100:
                raise ValueError("Learned-rule limit reached")
            rules.append(rule)
            self.projects_db.execute("INSERT OR REPLACE INTO user_learned_rules(id,body) VALUES(1,?)", (json.dumps(rules, ensure_ascii=False),))
            self.projects_db.commit()
            return {"rule_count": len(rules), "rules": rules}

    def optimize(self, query, skill_ids):
        if not isinstance(skill_ids, list) or not 1 <= len(skill_ids) <= 8 or any(not isinstance(item, str) for item in skill_ids):
            raise ValueError("skill_ids must contain between 1 and 8 strings")
        matches = self.search(query, limit=10)
        selected = [self.manifest(skill_id) for skill_id in dict.fromkeys(skill_ids)]
        learned = self.learned_rules()
        for manifest in selected:
            manifest["verification_contract"]["user_learned_rules"] = list(learned)
        builders = [manifest["builder_instructions"] for manifest in selected]
        challenges = []
        for manifest in selected:
            checks = manifest["challenger_rubric"].get("checks", [])
            if isinstance(checks, list):
                challenges.extend(str(check) for check in checks)
        return {
            "matches": matches,
            "selected": selected,
            "static_system_prefix": "\n\n---\n\n".join(builders),
            "challenger_prefix": "\n".join(challenges),
            "verification_contracts": [manifest["verification_contract"] for manifest in selected],
            "learned_rules": learned,
        }

    def close(self):
        self.db.close()
