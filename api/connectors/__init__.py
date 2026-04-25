"""Connector framework for SentioCap."""
from .base import BaseConnector, SyncResult
from .mock_salesforce import MockSalesforceConnector
from .mock_jira import MockJiraConnector

__all__ = ["BaseConnector", "SyncResult", "MockSalesforceConnector", "MockJiraConnector"]
