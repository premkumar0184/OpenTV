"""
OpenTV Structured Audit Logging Engine.
PROJECT.md Feature F3.8:
Captures every debloat action, timestamp, target device, previous state,
exit code, verification result, and rollback command in:
- audit_log.json (Machine-readable JSON Lines / JSON array)
- audit_log.txt  (Human-readable formatted audit trail)
"""
from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


@dataclass
class AuditEvent:
    """Represents a discrete debloat/rollback action event."""
    action: str                               # e.g. "DISABLE_PACKAGE", "ENABLE_PACKAGE", "ROLLBACK", "SET_HOME"
    package_name: str                         # Target package identifier
    device_id: str                            # ADB serial or IP:port (e.g. "192.168.1.50:5555")
    timestamp: str = ""                       # ISO-8601 UTC timestamp string
    brand_profile: str = "generic"            # Detected brand ID
    category: str = "safe"                    # Safety category ("never", "keep", "safe", "review")
    previous_state: str = "unknown"           # "enabled", "disabled", "unknown"
    new_state: str = "unknown"                # "disabled", "enabled"
    command: str = ""                         # Executed shell command
    exit_code: int = 0                        # Process exit code
    verification_command: str = ""            # Command used to verify
    verified: bool = True                     # Whether post-condition verification succeeded
    rollback_command: str = ""                # Command to reverse the operation
    user_confirmed: bool = True               # Whether operation was confirmed
    status: str = "SUCCESS"                   # "SUCCESS", "FAILED", "WARNING", "SKIPPED"
    details: Optional[str] = None             # Extra logs, errors, or context

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary, filtering None details."""
        d = asdict(self)
        if self.details is None:
            del d["details"]
        return d

    def format_text(self) -> str:
        """Format event into human-readable text block."""
        lines = [
            f"[{self.timestamp}] ACTION: {self.action}",
            f"  Target: {self.device_id} (Brand: {self.brand_profile.upper()})",
            f"  Package: {self.package_name} (Category: {self.category})",
            f"  Result: {self.status} (exit code {self.exit_code})",
            f"  State: {self.previous_state} -> {self.new_state} (Verified: {'YES' if self.verified else 'NO'})",
        ]
        if self.command:
            lines.append(f"  Command: {self.command}")
        if self.rollback_command:
            lines.append(f"  Rollback Command: {self.rollback_command}")
        if self.details:
            lines.append(f"  Details: {self.details}")
        lines.append("")
        return "\n".join(lines)


class AuditLogger:
    """Thread-safe dual logger for OpenTV debloat actions."""

    def __init__(
        self,
        log_dir: Union[Path, str] = ".",
        json_filename: str = "audit_log.json",
        txt_filename: str = "audit_log.txt",
    ) -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.json_path = self.log_dir / json_filename
        self.txt_path = self.log_dir / txt_filename
        self._lock = threading.Lock()

    def log(self, event: Union[AuditEvent, Dict[str, Any]]) -> AuditEvent:
        """
        Record an audit event to both audit_log.json (JSONL) and audit_log.txt.
        Thread-safe append operation.
        """
        if isinstance(event, dict):
            ev = AuditEvent(
                action=event.get("action", "UNKNOWN_ACTION"),
                package_name=event.get("package_name", event.get("package", "unknown")),
                device_id=event.get("device_id", "default"),
                timestamp=event.get("timestamp", datetime.now(timezone.utc).isoformat()),
                brand_profile=event.get("brand_profile", "generic"),
                category=event.get("category", "safe"),
                previous_state=event.get("previous_state", "unknown"),
                new_state=event.get("new_state", event.get("status", "unknown")),
                command=event.get("command", ""),
                exit_code=event.get("exit_code", 0),
                verification_command=event.get("verification_command", ""),
                verified=event.get("verified", True),
                rollback_command=event.get("rollback_command", ""),
                user_confirmed=event.get("user_confirmed", True),
                status=event.get("status", "SUCCESS"),
                details=event.get("details", None),
            )
        else:
            ev = event

        json_record = json.dumps(ev.to_dict())
        text_record = ev.format_text()

        with self._lock:
            with open(self.json_path, "a", encoding="utf-8") as f_json:
                f_json.write(json_record + "\n")

            with open(self.txt_path, "a", encoding="utf-8") as f_txt:
                f_txt.write(text_record)

        return ev

    def record_disable(
        self,
        device_id: str,
        package_name: str,
        brand_profile: str = "generic",
        category: str = "safe",
        exit_code: int = 0,
        verified: bool = True,
        command: str = "",
        rollback_command: str = "",
        details: Optional[str] = None,
    ) -> AuditEvent:
        """Convenience method to record a package disable action."""
        if not command:
            dev_flag = f"-s {device_id} " if device_id else ""
            command = f"adb {dev_flag}shell pm disable-user --user 0 {package_name}"
        if not rollback_command:
            dev_flag = f"-s {device_id} " if device_id else ""
            rollback_command = f"adb {dev_flag}shell pm enable {package_name}"

        status = "SUCCESS" if exit_code == 0 and verified else "FAILED"
        ev = AuditEvent(
            action="DISABLE_PACKAGE",
            package_name=package_name,
            device_id=device_id,
            brand_profile=brand_profile,
            category=category,
            previous_state="enabled",
            new_state="disabled",
            command=command,
            exit_code=exit_code,
            verified=verified,
            rollback_command=rollback_command,
            status=status,
            details=details,
        )
        return self.log(ev)

    def record_enable(
        self,
        device_id: str,
        package_name: str,
        brand_profile: str = "generic",
        exit_code: int = 0,
        verified: bool = True,
        command: str = "",
        details: Optional[str] = None,
    ) -> AuditEvent:
        """Convenience method to record a package restore/enable action."""
        if not command:
            dev_flag = f"-s {device_id} " if device_id else ""
            command = f"adb {dev_flag}shell pm enable {package_name}"

        status = "SUCCESS" if exit_code == 0 and verified else "FAILED"
        ev = AuditEvent(
            action="ENABLE_PACKAGE",
            package_name=package_name,
            device_id=device_id,
            brand_profile=brand_profile,
            category="safe",
            previous_state="disabled",
            new_state="enabled",
            command=command,
            exit_code=exit_code,
            verified=verified,
            rollback_command="",
            status=status,
            details=details,
        )
        return self.log(ev)

    def read_events(self) -> List[Dict[str, Any]]:
        """
        Read all logged events from audit_log.json.
        Seamlessly handles both JSON Lines (one JSON per line) and JSON array formats.
        """
        if not self.json_path.exists():
            return []

        content = self.json_path.read_text(encoding="utf-8").strip()
        if not content:
            return []

        # Check if content is formatted as a full JSON array
        if content.startswith("[") and content.endswith("]"):
            try:
                data = json.loads(content)
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass

        # Otherwise parse line-by-line JSONL
        events: List[Dict[str, Any]] = []
        for line in content.splitlines():
            line_str = line.strip()
            if line_str:
                try:
                    events.append(json.loads(line_str))
                except json.JSONDecodeError:
                    continue
        return events

    def clear(self) -> None:
        """Clear audit log files."""
        with self._lock:
            if self.json_path.exists():
                self.json_path.unlink()
            if self.txt_path.exists():
                self.txt_path.unlink()
