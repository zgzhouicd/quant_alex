# -*- coding: utf-8 -*-
"""
===================================
Analysis Integration Tests
===================================

Covers:
- API endpoint /analyze
- Name resolution to code
- Task queue submission
- Metadata persistence (original_query, selection_source)
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from api.app import create_app
from src.services.task_queue import AnalysisTaskQueue, TaskStatus
from src.config import Config
import src.auth as auth

@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


@pytest.fixture(autouse=True)
def disable_auth():
    """Keep analysis integration tests independent from local auth env state."""
    auth._auth_enabled = None
    with patch("api.middlewares.auth.is_auth_enabled", return_value=False), \
         patch("src.auth.is_auth_enabled", return_value=False):
        yield
    auth._auth_enabled = None

@pytest.fixture
def mock_task_queue():
    with patch("api.v1.endpoints.analysis.get_task_queue") as mock_get:
        queue = MagicMock(spec=AnalysisTaskQueue)
        mock_get.return_value = queue
        yield queue

class TestAnalysisIntegration:
    """End-to-end integration tests for the analysis flow."""

    def test_trigger_analysis_flow_manual_symbol(self, client, mock_task_queue):
        """Test flow: User enters a US symbol -> task submitted."""
        # Setup mock behavior
        mock_task_queue.submit_tasks_batch.return_value = (
            [MagicMock(task_id="test_task_123", stock_code="AAPL")],
            []
        )

        # Trigger analysis with a US symbol
        response = client.post(
            "/api/v1/analysis/analyze",
            json={
                "stock_code": "AAPL",
                "async_mode": True,
                "original_query": "AAPL",
                "selection_source": "manual"
            }
        )

        assert response.status_code == 202
        data = response.json()
        assert data["task_id"] == "test_task_123"
        assert data["status"] == "pending"

        # Verify task queue received the correct resolved code and metadata.
        # Use call_args so this integration test stays focused on analysis flow
        # semantics even if the queue API gains orthogonal optional flags.
        mock_task_queue.submit_tasks_batch.assert_called_once()
        _, kwargs = mock_task_queue.submit_tasks_batch.call_args
        assert kwargs["stock_codes"] == ["AAPL"]
        assert kwargs["stock_name"] is None
        assert kwargs["original_query"] == "AAPL"
        assert kwargs["selection_source"] == "manual"
        assert kwargs["report_type"] == "detailed"
        assert kwargs["force_refresh"] is False
        assert kwargs["notify"] is False
        assert kwargs["instruments_by_code"]["AAPL"]["asset_class"] == "us_equity"

    def test_trigger_analysis_batch_deduplication(self, client, mock_task_queue):
        """Test de-duplication across case variants (AAPL and aapl)."""
        mock_task_queue.submit_tasks_batch.return_value = ([], [])

        client.post(
            "/api/v1/analysis/analyze",
            json={
                "stock_codes": ["AAPL", "aapl"],
                "async_mode": True
            }
        )

        # Should only submit once after de-duplication
        mock_task_queue.submit_tasks_batch.assert_called_once()
        args, kwargs = mock_task_queue.submit_tasks_batch.call_args
        assert len(kwargs["stock_codes"]) == 1
        assert kwargs["stock_codes"] == ["AAPL"]

    def test_trigger_analysis_dos_protection(self, client):
        """Test that excessive batch size is rejected after instrument resolution."""
        # Use `symbols` + valid US-style tickers so resolution succeeds; limit is enforced post-resolve.
        too_many = [f"TI{i:02d}" for i in range(51)]
        response = client.post(
            "/api/v1/analysis/analyze",
            json={
                "symbols": too_many,
                "async_mode": True
            }
        )

        assert response.status_code == 400
        assert "最多支持" in response.json()["message"]

    def test_trigger_analysis_metadata_isolation_in_batch(self, client, mock_task_queue):
        """Test that single-stock metadata isn't applied to batch tasks."""
        mock_task_queue.submit_tasks_batch.return_value = ([], [])

        client.post(
            "/api/v1/analysis/analyze",
            json={
                "stock_codes": ["AAPL", "TSLA"],
                "stock_name": "Apple",
                "original_query": "AAPL",
                "async_mode": True
            }
        )

        # Batch request: metadata should be None
        mock_task_queue.submit_tasks_batch.assert_called_once()
        args, kwargs = mock_task_queue.submit_tasks_batch.call_args
        assert kwargs["stock_name"] is None
        assert kwargs["original_query"] is None
        assert kwargs["selection_source"] is None
