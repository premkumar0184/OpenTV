"""
OpenTV Core Subpackage: Configuration, ADB client, device models, and launcher deployer.
"""

from .adb import AdbClient, AdbDevice, AdbWrapper
from .config import (
    DEFAULT_APPS,
    DEFAULT_QUICK_SETTINGS,
    DEFAULT_THEME,
    SUPPORTED_SCHEMA_VERSION,
    HdmiInputConfig,
    LauncherConfig,
    OledProtectionConfig,
    create_default_config,
)
from .deployer import (
    ApkInstallError,
    ConfigPushError,
    DeployResult,
    DeploySummary,
    DeployerError,
    HomeActivityError,
    HomeVerificationError,
    LauncherDeployer,
)
from .device import (
    ActivityComponent,
    AmbiguousDeviceError,
    DeviceConnectionError,
    DeviceError,
    DeviceInfo,
    DeviceInterrogationError,
    DeviceManager,
    NoDeviceConnectedError,
    PackageInfo,
)

__all__ = [
    # Config
    "LauncherConfig",
    "HdmiInputConfig",
    "OledProtectionConfig",
    "create_default_config",
    "SUPPORTED_SCHEMA_VERSION",
    "DEFAULT_THEME",
    "DEFAULT_APPS",
    "DEFAULT_QUICK_SETTINGS",
    # ADB
    "AdbWrapper",
    "AdbClient",
    "AdbDevice",
    # Device
    "ActivityComponent",
    "PackageInfo",
    "DeviceInfo",
    "DeviceManager",
    "DeviceError",
    "NoDeviceConnectedError",
    "AmbiguousDeviceError",
    "DeviceConnectionError",
    "DeviceInterrogationError",
    # Deployer
    "DeployResult",
    "DeploySummary",
    "LauncherDeployer",
    "DeployerError",
    "ApkInstallError",
    "ConfigPushError",
    "HomeActivityError",
    "HomeVerificationError",
]
