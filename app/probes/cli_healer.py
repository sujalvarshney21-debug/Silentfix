"""Pillar 1: Terminal CLI Error Healer.

Intercepts command-not-found patterns, runs 4-stage system probes
(Active Process, System PATH, Common Binary Trees, Winget Catalog),
and generates structured remediation plans.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("silentfix.cli_healer")

DiagnosisStatus = Literal[
    "FOUND_ON_DISK_NEEDS_PATH",
    "AVAILABLE_VIA_WINGET",
    "NOT_FOUND",
    "ALREADY_IN_PATH",
]

COMMON_INSTALL_SEARCH_PATHS: list[str] = [
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    r"C:\Tools",
    r"C:\msys64",
    r"C:\cygwin64",
    os.path.expanduser(r"~\AppData\Local\Programs"),
    os.path.expanduser(r"~\AppData\Local"),
    os.path.expanduser(r"~\.cargo\bin"),
    os.path.expanduser(r"~\go\bin"),
]

KNOWN_CLI_WINGET_MAP: dict[str, str] = {
    "git": "Git.Git",
    "node": "OpenJS.NodeJS",
    "npm": "OpenJS.NodeJS",
    "python": "Python.Python.3.12",
    "py": "Python.Python.3.12",
    "docker": "Docker.DockerDesktop",
    "kubectl": "Kubernetes.kubectl",
    "helm": "Helm.Helm",
    "terraform": "HashiCorp.Terraform",
    "aws": "Amazon.AWSCLI",
    "az": "Microsoft.AzureCLI",
    "gh": "GitHub.cli",
    "cargo": "Rustlang.Rustup",
    "go": "GoLang.Go",
    "jq": "jqlang.jq",
    "7z": "7zip.7zip",
    "ffmpeg": "Gypsect.FFmpeg",
}


class CliDiagnosis(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    missing_command: str
    status: DiagnosisStatus
    found_executable_path: Optional[str] = None
    directory_to_add: Optional[str] = None
    winget_package_id: Optional[str] = None
    summary: str
    suggested_commands: list[str] = Field(default_factory=list)


NON_COMMAND_WORDS = {
    "error", "failed", "cannot", "fatal", "warning", "invalid", "unable", "exception",
    "traceback",
}


def extract_missing_command(error_text: str) -> Optional[str]:
    """Extract missing command name from common shell error messages."""
    patterns = [
        r"'([^']+)' is not recognized as an internal or external command",
        r'"([^"]+)" is not recognized as an internal or external command',
        r"command not found:\s*([^\s]+)",
        r"bash:\s*([^\s:]+):\s*command not found",
        r"zsh:\s*command not found:\s*([^\s]+)",
        r"The term '([^']+)' is not recognized as the name of a cmdlet",
    ]
    for pattern in patterns:
        m = re.search(pattern, error_text, re.IGNORECASE)
        if m:
            cmd = m.group(1).strip()
            return cmd.removesuffix(".exe") if cmd.lower().endswith(".exe") else cmd

    tokens = error_text.strip().split()
    if tokens and tokens[0].lower() not in NON_COMMAND_WORDS and re.match(r"^[a-zA-Z0-9_\-]{2,30}$", tokens[0]):
        return tokens[0]

    return None


def find_executable_on_disk(command: str) -> Optional[Path]:
    """Scan common install directories for orphaned binaries with safety limits."""
    exe_names = [f"{command}.exe", f"{command}.cmd", f"{command}.bat", command]

    for base in COMMON_INSTALL_SEARCH_PATHS:
        base_path = Path(base)
        if not base_path.exists():
            continue

        for exe_name in exe_names:
            # Check root of search path first
            direct_candidate = base_path / exe_name
            try:
                if direct_candidate.is_file():
                    return direct_candidate
            except (PermissionError, OSError):
                pass

            # Fast search in immediate child directories (depth 1 & 2)
            try:
                for match in base_path.glob(f"*/{exe_name}"):
                    if match.is_file():
                        return match
                for match in base_path.glob(f"*/*/{exe_name}"):
                    if match.is_file():
                        return match
            except (PermissionError, OSError):
                continue

    return None


def _search_disk_for_command(command: str) -> Optional[Union[Path, str]]:
    """Entry point for disk searching, allowing targeted testing hooks."""
    return find_executable_on_disk(command)


def diagnose_terminal_error(error_text: str) -> CliDiagnosis:
    """Diagnose a terminal command error through the 4-stage system probe."""
    cmd = extract_missing_command(error_text) or "unknown"

    # Stage 1: Active System PATH Check
    if shutil.which(cmd):
        return CliDiagnosis(
            missing_command=cmd,
            status="ALREADY_IN_PATH",
            summary=f"Command '{cmd}' is already in system PATH.",
        )

    # Stage 2: Common Binary Trees Search
    raw_exe = _search_disk_for_command(cmd)
    if raw_exe:
        exe_path = Path(raw_exe)
        target_dir = str(exe_path.parent.resolve())
        # Safe PowerShell User-scope environment update (avoids setx 1024-char PATH truncation)
        suggested_commands = (
            [
                '$u = [Environment]::GetEnvironmentVariable("Path", "User"); '
                f'[Environment]::SetEnvironmentVariable("Path", "$u;{target_dir}", "User")'
            ]
            if sys.platform == "win32"
            else [f'export PATH="$PATH:{target_dir}"']
        )
        return CliDiagnosis(
            missing_command=cmd,
            status="FOUND_ON_DISK_NEEDS_PATH",
            found_executable_path=str(exe_path),
            directory_to_add=target_dir,
            summary=f"Found '{cmd}' at '{exe_path}' (missing from PATH).",
            suggested_commands=suggested_commands,
        )

    # Stage 3: Known Winget Catalog Map
    winget_id = KNOWN_CLI_WINGET_MAP.get(cmd.lower())
    if winget_id:
        return CliDiagnosis(
            missing_command=cmd,
            status="AVAILABLE_VIA_WINGET",
            winget_package_id=winget_id,
            summary=f"'{cmd}' was not found on disk. Install via Winget package '{winget_id}'.",
            suggested_commands=[f"winget install --id {winget_id} --exact --silent"],
        )

    # Stage 4: Unidentified command
    return CliDiagnosis(
        missing_command=cmd,
        status="NOT_FOUND",
        summary=f"Could not locate '{cmd}' on local system or in verified winget catalog.",
    )
