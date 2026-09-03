"""
Tests for PipelineStep base class and PipelineContext.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from core.pipeline.steps.base import PipelineStep, PipelineContext, PipelineResult


class TestPipelineStep(PipelineStep):
    """Concrete implementation for testing."""

    def __init__(self, name: str = "TestStep"):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    async def execute(self, context: PipelineContext) -> None:
        context.add_warning("Test warning")


class TestPipelineContext:
    """Tests for PipelineContext."""

    def test_default_values(self):
        """Test default values are set correctly."""
        ctx = PipelineContext()
        assert ctx.products == []
        assert ctx.pricing_data == {}
        assert ctx.calculation_results == {}
        assert ctx.price_updates == []
        assert ctx.api_results == {}
        assert ctx.updates_for_excel == []
        assert ctx.errors == []
        assert ctx.warnings == []
        assert ctx.dry_run is False
        assert ctx.current_time is None
        assert ctx.should_stop is False
        assert ctx.progress_callback is None
        assert ctx.request_id is None

    def test_add_error(self):
        """Test adding errors."""
        ctx = PipelineContext()
        ctx.add_error("Test error")
        assert "Test error" in ctx.errors

    def test_add_warning(self):
        """Test adding warnings."""
        ctx = PipelineContext()
        ctx.add_warning("Test warning")
        assert "Test warning" in ctx.warnings

    def test_set_total_steps(self):
        """Test setting total steps."""
        ctx = PipelineContext()
        ctx.set_total_steps(10)
        assert ctx._total_steps == 10

    def test_report_progress_without_callback(self):
        """Test report_progress without callback doesn't crash."""
        ctx = PipelineContext()
        ctx.set_total_steps(5)
        ctx.report_progress(2, "Step 2 message")
        assert ctx._current_step == 2

    def test_report_progress_with_callback(self):
        """Test report_progress calls callback."""
        ctx = PipelineContext()
        ctx.set_total_steps(5)
        callback = MagicMock()
        ctx.progress_callback = callback
        ctx.report_progress(3, "Step 3 message")
        callback.assert_called_once_with(3, 5, "Step 3 message")


class TestPipelineStepBase:
    """Tests for PipelineStep abstract base class."""

    def test_cannot_instantiate_abstract(self):
        """Test that PipelineStep cannot be instantiated directly."""
        with pytest.raises(TypeError):
            PipelineStep()  # type: ignore[abstract]

    def test_concrete_step_works(self):
        """Test concrete step implementation works."""
        step = TestPipelineStep("MyStep")
        assert step.name == "MyStep"

    @pytest.mark.asyncio
    async def test_execute_called(self):
        """Test execute method is called."""
        step = TestPipelineStep()
        ctx = PipelineContext()
        await step.execute(ctx)
        assert "Test warning" in ctx.warnings