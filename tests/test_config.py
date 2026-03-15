from __future__ import annotations

import logging
import io
import unittest

from echobot.config import (
    _configure_loguru_reme_logging,
    configure_runtime_logging,
)


class RuntimeLoggingConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reme_logger = logging.getLogger("reme")
        self.as_logger = logging.getLogger("as")
        self.original_reme_level = self.reme_logger.level
        self.original_as_level = self.as_logger.level
        self.original_reme_handler_levels = [handler.level for handler in self.reme_logger.handlers]
        self.original_as_handler_levels = [handler.level for handler in self.as_logger.handlers]

    def tearDown(self) -> None:
        self.reme_logger.setLevel(self.original_reme_level)
        for handler, level in zip(self.reme_logger.handlers, self.original_reme_handler_levels):
            handler.setLevel(level)

        self.as_logger.setLevel(self.original_as_level)
        for handler, level in zip(self.as_logger.handlers, self.original_as_handler_levels):
            handler.setLevel(level)

    def test_configure_runtime_logging_updates_reme_logger_level(self) -> None:
        configure_runtime_logging({"REME_LOG_LEVEL": "WARNING"})

        self.assertEqual(logging.WARNING, self.reme_logger.level)
        for handler in self.reme_logger.handlers:
            self.assertEqual(logging.WARNING, handler.level)

    def test_configure_runtime_logging_updates_agentscope_logger_level(self) -> None:
        configure_runtime_logging({"AGENTSCOPE_LOG_LEVEL": "ERROR"})

        self.assertEqual(logging.ERROR, self.as_logger.level)
        for handler in self.as_logger.handlers:
            self.assertEqual(logging.ERROR, handler.level)

    def test_configure_runtime_logging_rejects_invalid_log_level(self) -> None:
        with self.assertRaisesRegex(ValueError, "REME_LOG_LEVEL must be one of"):
            configure_runtime_logging({"REME_LOG_LEVEL": "QUIET"})

    def test_configure_loguru_reme_logging_suppresses_reme_info(self) -> None:
        try:
            from loguru import logger
        except ImportError:
            self.skipTest("loguru is not installed")

        stream = io.StringIO()
        _configure_loguru_reme_logging("WARNING", sink=stream)

        reme_logger = logger.patch(
            lambda record: record.update(name="reme.core.utils.pydantic_config_parser")
        )
        other_logger = logger.patch(lambda record: record.update(name="demo.module"))

        reme_logger.info("hidden info")
        reme_logger.warning("visible warning")
        other_logger.info("other info")

        output = stream.getvalue()
        self.assertNotIn("hidden info", output)
        self.assertIn("visible warning", output)
        self.assertIn("other info", output)
