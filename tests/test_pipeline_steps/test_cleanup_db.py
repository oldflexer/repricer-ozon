"""
Tests for CleanupDatabaseStep.
"""
import pytest
from unittest.mock import MagicMock
from core.pipeline.steps.cleanup_db import CleanupDatabaseStep
from core.pipeline.steps.base import PipelineContext


class TestCleanupDatabaseStep:
    """Tests for CleanupDatabaseStep."""

    @pytest.fixture
    def step(self, mock_maintenance_repo):
        return CleanupDatabaseStep(maintenance_repo=mock_maintenance_repo)

    @pytest.mark.asyncio
    async def test_execute_success(self, step, mock_maintenance_repo, pipeline_context):
        """Test successful database cleanup."""
        mock_maintenance_repo.auto_cleanup_if_needed.return_value = 42

        await step.execute(pipeline_context)

        mock_maintenance_repo.auto_cleanup_if_needed.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_no_cleanup_needed(self, step, mock_maintenance_repo, pipeline_context):
        """Test when no cleanup is needed."""
        mock_maintenance_repo.auto_cleanup_if_needed.return_value = 0

        await step.execute(pipeline_context)

        mock_maintenance_repo.auto_cleanup_if_needed.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_error_handling(self, step, mock_maintenance_repo, pipeline_context):
        """Test error handling when cleanup fails."""
        mock_maintenance_repo.auto_cleanup_if_needed.side_effect = Exception("DB Error")

        await step.execute(pipeline_context)

        assert len(pipeline_context.warnings) == 1
        assert "Database cleanup failed" in pipeline_context.warnings[0]
        # should_stop should NOT be True for cleanup failures
        assert pipeline_context.should_stop is False