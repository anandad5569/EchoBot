from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from echobot.orchestration import RoleCardRegistry
from echobot.orchestration.roles import DEFAULT_ROLE_PROMPT


class RoleCardRegistryTests(unittest.TestCase):
    def test_discover_creates_default_role_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)

            registry = RoleCardRegistry.discover(project_root=workspace)

            default_path = workspace / ".echobot" / "roles" / "default.md"
            self.assertTrue(default_path.exists())
            self.assertEqual(DEFAULT_ROLE_PROMPT, default_path.read_text(encoding="utf-8").strip())
            self.assertEqual(DEFAULT_ROLE_PROMPT, registry.require("default").prompt)

    def test_discover_uses_existing_workspace_default_role_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            default_path = workspace / ".echobot" / "roles" / "default.md"
            default_path.parent.mkdir(parents=True, exist_ok=True)
            default_path.write_text("# Default Role\n\n这是自定义默认角色。", encoding="utf-8")

            registry = RoleCardRegistry.discover(project_root=workspace)

            self.assertEqual(
                "# Default Role\n\n这是自定义默认角色。",
                registry.require(None).prompt,
            )

    def test_workspace_default_role_has_highest_priority(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            project_roles = workspace / "roles"
            workspace_roles = workspace / ".echobot" / "roles"
            project_roles.mkdir(parents=True, exist_ok=True)
            workspace_roles.mkdir(parents=True, exist_ok=True)
            (project_roles / "default.md").write_text(
                "# Default Role\n\n这是 project roles 里的默认角色。",
                encoding="utf-8",
            )
            (workspace_roles / "default.md").write_text(
                "# Default Role\n\n这是 .echobot roles 里的默认角色。",
                encoding="utf-8",
            )

            registry = RoleCardRegistry.discover(project_root=workspace)

            self.assertEqual(
                "# Default Role\n\n这是 .echobot roles 里的默认角色。",
                registry.require("default").prompt,
            )
