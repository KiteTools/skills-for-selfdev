from __future__ import annotations

import importlib.util
import json
import stat
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


install = load_module("portable_install", SKILL_ROOT / "scripts" / "install.py")
verify = load_module("portable_verify", SKILL_ROOT / "scripts" / "verify.py")


def personalized_context() -> dict:
    return {
        "schema_version": 1,
        "status": "active",
        "focus_until": "2099-12-31",
        "active_understanding": "Живое понимание",
        "l1": {"status": "active", "text": "Большая цель"},
        "questions": {"morning": "Утренний вопрос?", "evening": "Вечерний вопрос?"},
        "warning_patterns": ["Спешка"],
        "viability_reflections": {
            "affirmations": ["Утверждение"],
            "understandings": ["Новое понимание"],
        },
        "focus_groups": [
            {
                "id": "main",
                "label": "Главное",
                "l2": "Способ",
                "period_focus": "Фокус периода",
            }
        ],
        "task_choices": [
            {
                "number": 1,
                "id": "task-001",
                "group_id": "main",
                "status": "active",
                "label": "Первая задача",
                "l2": "Способ",
                "period_focus": "Фокус периода",
                "day_result": "Готовый результат",
                "first_step": "Первый шаг",
                "duration_minutes": 30,
            }
        ],
    }


class InstallAndVerifyTests(unittest.TestCase):
    def test_context_markers_are_rejected(self) -> None:
        template = json.loads(
            (SKILL_ROOT / "assets" / "templates" / "active_context.json").read_text(
                encoding="utf-8"
            )
        )
        with self.assertRaisesRegex(ValueError, "REPLACE_WITH_YOUR"):
            install.validate_context(template)

    def test_install_builds_private_local_layout_and_schedule_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "assistant"
            data = root / "private"
            summaries = root / "summaries"
            sessions = root / "sessions"
            token = root / "telegram.token"
            context_path = root / "context.json"
            config = root / "openclaw.json"
            token.write_text("not-a-real-token\n", encoding="utf-8")
            token.chmod(stat.S_IRUSR | stat.S_IWUSR)
            context_path.write_text(
                json.dumps(personalized_context(), ensure_ascii=False), encoding="utf-8"
            )
            config.write_text("{}\n", encoding="utf-8")

            options = install.InstallOptions(
                project_root=project,
                data_dir=data,
                context_json=context_path,
                summaries_dir=summaries,
                timezone="Europe/Lisbon",
                owner_telegram_id="10001",
                telegram_target="10001",
                openclaw_config=config,
                openclaw_sessions_dir=sessions,
                token_file=token,
                thread_cleanup_cutoff="2099-01-01T00:00:00Z",
                python_bin="python3",
            )
            plan = install.build_plan(options)
            self.assertFalse(project.exists())
            self.assertEqual(len(plan["schedules"]), 7)

            install.apply_install(options, plan)
            self.assertTrue((project / "scripts" / "personal_daily_system.py").is_file())
            self.assertTrue((project / "AGENTS.md").is_file())
            self.assertTrue((data / "events.jsonl").is_file())
            self.assertEqual(stat.S_IMODE(data.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((data / "events.jsonl").stat().st_mode), 0o600)

            declarations = json.loads(
                (project / "setup" / "schedule-declarations.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(len(declarations["schedules"]), 7)
            self.assertEqual(
                declarations["schedules"][0]["declaration_key"],
                "personal-daily-preflight-0300",
            )
            fragment = json.loads(
                (project / "setup" / "openclaw-plugin-fragment.json").read_text(
                    encoding="utf-8"
                )
            )
            plugin = fragment["plugins"]["entries"]["personal-daily-transport"]
            self.assertEqual(plugin["config"]["ownerTelegramId"], "10001")
            self.assertIs(plugin["config"]["technicalCleanupEnabled"], False)
            self.assertNotIn("not-a-real-token", json.dumps(fragment))

            report = verify.verify_installation(
                project_root=project,
                data_dir=data,
                token_file=token,
                openclaw_config=None,
            )
            self.assertTrue(report["ok"], report)

    def test_private_data_must_be_outside_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "assistant"
            with self.assertRaisesRegex(ValueError, "outside"):
                install.ensure_data_outside_project(project, project / "private")


if __name__ == "__main__":
    unittest.main()
