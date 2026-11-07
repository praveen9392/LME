"""
Backward-compatibility adapter for JobFilterPipeline2.
"""
from __future__ import annotations

from backend.services.job_matching_service import JobMatchingService

# Alias JobFilterPipeline2 to JobMatchingService
JobFilterPipeline2 = JobMatchingService
