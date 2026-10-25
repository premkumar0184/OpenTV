"""
OpenTV Launcher Deployer.
PROJECT.md Feature F2.6:
Handles APK installation, dual-storage configuration push, Home activity registration,
Home verification, and live configuration reload broadcasting.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from opentv.core.adb import AdbClient, AdbWrapper
from opentv.core.config import LauncherConfig


@dataclass
class DeployResult:
    """Outcome of a single launcher deployment step."""

    step: str
    success: bool
    message: str
    return_code: int = 0
    output: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "success": self.success,
            "message": self.message,
            "return_code": self.return_code,
            "output": self.output,
            "details": self.details,
        }


@dataclass
class DeploySummary:
    """Composite report of all deployment steps in a pipeline."""

    serial: str
    steps: List[DeployResult] = field(default_factory=list)
    overall_success: bool = True
    error_message: Optional[str] = None

    def add_result(self, result: DeployResult) -> None:
        self.steps.append(result)
        if not result.success:
            self.overall_success = False
            if not self.error_message:
                self.error_message = f"Step '{result.step}' failed: {result.message}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "serial": self.serial,
            "overall_success": self.overall_success,
            "error_message": self.error_message,
            "steps": [s.to_dict() for s in self.steps],
        }


class DeployerError(Exception):
    """Base exception for deployment operations."""

    pass


class ApkInstallError(DeployerError):
    """Raised when APK installation fails."""

    pass


class ConfigPushError(DeployerError):
    """Raised when serializing or pushing config JSON fails."""

    pass


class HomeActivityError(DeployerError):
    """Raised when setting the default Home activity fails."""

    pass


class HomeVerificationError(DeployerError):
    """Raised when Home activity does not resolve to the expected launcher."""

    pass


class LauncherDeployer:
    """
    Orchestrates the deployment, configuration push, Home activity registration,
    and live reload of the OpenTV Launcher on target Android TV devices.
    """

    DEFAULT_HOME_COMPONENT = "org.opentv.launcher/.MainActivity"
    PRIMARY_CONFIG_PATH = "/sdcard/Android/data/org.opentv.launcher/files/config.json"
    SECONDARY_CONFIG_PATH = "/sdcard/OpenTV/config.json"
    BROADCAST_RELOAD_ACTION = "org.opentv.launcher.RELOAD_CONFIG"

    def __init__(
        self,
        adb_wrapper: Optional[AdbWrapper] = None,
        default_serial: Optional[str] = None,
        runner: Optional[Any] = None,
    ) -> None:
        self.adb = adb_wrapper or AdbWrapper(default_device=default_serial)
        self.default_serial = default_serial
        self.runner = runner  # Optional MockAdbRunner or custom executor

    def _run_cmd(
        self, cmd: List[str], timeout: Optional[float] = 60.0
    ) -> Tuple[int, str, str]:
        """Executes an ADB command via injected runner or standard subprocess."""
        if self.runner is not None:
            if hasattr(self.runner, "execute"):
                return self.runner.execute(cmd)
            elif callable(self.runner):
                return self.runner(cmd)
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return (res.returncode, res.stdout, res.stderr)
        except FileNotFoundError:
            return (127, "", f"ADB binary not found: '{cmd[0]}'")
        except subprocess.TimeoutExpired:
            return (124, "", f"Command timed out after {timeout}s: {' '.join(cmd)}")
        except Exception as e:
            return (1, "", str(e))

    def _resolve_target(self, serial: Optional[str]) -> str:
        target = serial or self.default_serial or self.adb.default_device
        if not target:
            raise DeployerError(
                "Target device serial must be specified for deployment operations."
            )
        return target

    # 1. APK Installation
    def install_apk(
        self,
        serial: Optional[str],
        apk_path: str,
        reinstall: bool = True,
        grant_permissions: bool = True,
    ) -> DeployResult:
        """
        Installs the OpenTV APK on the target device via `adb install -r [-g] <path>`.
        Handles fallback if -g is not supported on older Android versions.
        """
        target = self._resolve_target(serial)
        p = Path(apk_path)
        # Note: In mock test environments, physical local files might be mocked
        if not p.exists() and self.runner is None:
            return DeployResult(
                step="install_apk",
                success=False,
                message=f"Local APK file not found at: {apk_path}",
                return_code=1,
            )

        cmd = [self.adb.adb_path, "-s", target, "install"]
        if reinstall:
            cmd.append("-r")
        if grant_permissions:
            cmd.append("-g")
        cmd.append(str(apk_path))

        code, out, err = self._run_cmd(cmd)
        combined = f"{out}\n{err}".strip()

        # If -g failed due to older Android version, retry with just -r
        if (
            code != 0
            and grant_permissions
            and ("Unknown option: -g" in combined or "bad option: -g" in combined)
        ):
            retry_cmd = [self.adb.adb_path, "-s", target, "install"]
            if reinstall:
                retry_cmd.append("-r")
            retry_cmd.append(str(apk_path))
            code, out, err = self._run_cmd(retry_cmd)
            combined = f"{out}\n{err}".strip()

        success = code == 0 and ("Success" in combined or "success" in combined.lower())
        msg = (
            "APK installed successfully"
            if success
            else f"Installation failed: {combined}"
        )

        return DeployResult(
            step="install_apk",
            success=success,
            message=msg,
            return_code=code,
            output=combined,
            details={"apk_path": str(apk_path), "target": target},
        )

    # 2. Configuration Serialization & Push
    def push_config(
        self,
        serial: Optional[str],
        config: Union[LauncherConfig, str, dict],
        remote_path: str = SECONDARY_CONFIG_PATH,
        copy_to_app_storage: bool = True,
    ) -> DeployResult:
        """
        Serializes configuration to temporary JSON file and pushes to TV storage via ADB.
        Optionally copies/pushes to scoped app directory `/sdcard/Android/data/org.opentv.launcher/files/config.json`.
        """
        target = self._resolve_target(serial)

        # 1. Prepare JSON string
        if isinstance(config, LauncherConfig):
            json_payload = config.to_json()
        elif isinstance(config, dict):
            json_payload = json.dumps(config, indent=2)
        elif isinstance(config, str):
            # Validate JSON string
            try:
                json.loads(config)
                json_payload = config
            except json.JSONDecodeError as e:
                return DeployResult(
                    step="push_config",
                    success=False,
                    message=f"Invalid JSON configuration string: {e}",
                    return_code=1,
                )
        else:
            return DeployResult(
                step="push_config",
                success=False,
                message=f"Unsupported config type: {type(config).__name__}",
                return_code=1,
            )

        # 2. Write to local temp file
        temp_file = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        try:
            temp_file.write(json_payload)
            temp_file.flush()
            temp_file.close()
            local_temp_path = temp_file.name

            # Ensure remote target directory exists
            remote_dir = str(Path(remote_path).parent).replace("\\", "/")
            mkdir_cmd = self.adb.build_shell_cmd(
                ["mkdir", "-p", remote_dir], target_device=target
            )
            self._run_cmd(mkdir_cmd)

            # 3. Push primary destination
            push_cmd = self.adb.build_push_config_cmd(
                local_temp_path, remote_path, target_device=target
            )
            code, out, err = self._run_cmd(push_cmd)
            combined = f"{out}\n{err}".strip()

            if code != 0:
                return DeployResult(
                    step="push_config",
                    success=False,
                    message=f"Failed to push config to {remote_path}: {combined}",
                    return_code=code,
                    output=combined,
                )

            pushed_paths = [remote_path]

            # 4. Push to scoped app storage if requested
            if copy_to_app_storage and remote_path != self.PRIMARY_CONFIG_PATH:
                app_dir = str(Path(self.PRIMARY_CONFIG_PATH).parent).replace("\\", "/")
                self._run_cmd(
                    self.adb.build_shell_cmd(["mkdir", "-p", app_dir], target_device=target)
                )
                app_push_cmd = self.adb.build_push_config_cmd(
                    local_temp_path, self.PRIMARY_CONFIG_PATH, target_device=target
                )
                app_code, _, _ = self._run_cmd(app_push_cmd)
                if app_code == 0:
                    pushed_paths.append(self.PRIMARY_CONFIG_PATH)

            return DeployResult(
                step="push_config",
                success=True,
                message=f"Config pushed successfully to {', '.join(pushed_paths)}",
                return_code=0,
                output=combined,
                details={"pushed_paths": pushed_paths, "target": target},
            )

        finally:
            Path(temp_file.name).unlink(missing_ok=True)

    # 3. Default Home Activity Registration
    def set_home_activity(
        self,
        serial: Optional[str],
        component: str = DEFAULT_HOME_COMPONENT,
    ) -> DeployResult:
        """
        Sets default Android TV Home activity via `adb shell cmd package set-home-activity <component>`.
        """
        target = self._resolve_target(serial)
        cmd = self.adb.build_set_home_cmd(component, target_device=target)
        code, out, err = self._run_cmd(cmd)
        combined = f"{out}\n{err}".strip()

        success = code == 0 and ("Success" in combined or combined == "")
        msg = (
            f"Default home activity set to '{component}'"
            if success
            else f"Failed to set home: {combined}"
        )

        return DeployResult(
            step="set_home_activity",
            success=success,
            message=msg,
            return_code=code,
            output=combined,
            details={"component": component, "target": target},
        )

    # 4. Configuration Reload Broadcast
    def reload_config(self, serial: Optional[str]) -> DeployResult:
        """
        Broadcasts `org.opentv.launcher.RELOAD_CONFIG` via `adb shell am broadcast` to trigger live reload.
        """
        target = self._resolve_target(serial)
        cmd = self.adb.build_broadcast_reload_cmd(target_device=target)
        code, out, err = self._run_cmd(cmd)
        combined = f"{out}\n{err}".strip()

        success = code == 0 and (
            "result=0" in combined
            or "Broadcast completed" in combined
            or combined == ""
        )
        msg = (
            "Broadcast reload triggered successfully"
            if success
            else f"Broadcast failed: {combined}"
        )

        return DeployResult(
            step="reload_config",
            success=success,
            message=msg,
            return_code=code,
            output=combined,
            details={"action": self.BROADCAST_RELOAD_ACTION, "target": target},
        )

    # 5. Home Activity Verification
    def verify_home(
        self,
        serial: Optional[str],
        expected_component: str = DEFAULT_HOME_COMPONENT,
    ) -> Tuple[bool, str]:
        """
        Verifies currently resolving Home activity via:
        `adb shell cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME`.
        Returns (is_opentv_home: bool, current_home_component: str).
        """
        target = self._resolve_target(serial)
        cmd = self.adb.build_resolve_home_cmd(target_device=target)
        code, out, _ = self._run_cmd(cmd)

        if code != 0 or not out.strip():
            return (False, "Unknown")

        current_component = "Unknown"
        for line in reversed(out.strip().splitlines()):
            line = line.strip()
            if "/" in line and not line.startswith("priority="):
                current_component = line
                break

        # Check if expected package/activity matches
        expected_pkg = expected_component.split("/")[0]
        is_matched = expected_pkg in current_component

        return (is_matched, current_component)

    # 6. Composite Deployment Pipeline
    def deploy_full(
        self,
        serial: Optional[str],
        config: Union[LauncherConfig, str, dict],
        apk_path: Optional[str] = None,
        set_home: bool = True,
        reload: bool = True,
    ) -> DeploySummary:
        """
        Executes end-to-end launcher deployment sequence:
        1. Install APK (if apk_path provided)
        2. Push config JSON
        3. Set Home activity (if set_home=True)
        4. Verify Home resolution
        5. Broadcast reload config (if reload=True)
        """
        target = self._resolve_target(serial)
        summary = DeploySummary(serial=target)

        # Step 1: Install APK
        if apk_path:
            res_install = self.install_apk(target, apk_path)
            summary.add_result(res_install)
            if not res_install.success:
                return summary

        # Step 2: Push Config
        res_push = self.push_config(target, config)
        summary.add_result(res_push)
        if not res_push.success:
            return summary

        # Step 3: Set Home Activity
        if set_home:
            res_home = self.set_home_activity(target)
            summary.add_result(res_home)

        # Step 4: Verify Home
        is_home, current_home = self.verify_home(target)
        res_verify = DeployResult(
            step="verify_home",
            success=is_home,
            message=(
                f"Resolving Home activity is '{current_home}'"
                if is_home
                else f"Warning: Home activity resolved to '{current_home}' instead of OpenTV"
            ),
            details={"current_home": current_home, "is_opentv": is_home},
        )
        summary.add_result(res_verify)

        # Step 5: Broadcast Reload
        if reload:
            res_reload = self.reload_config(target)
            summary.add_result(res_reload)

        return summary
