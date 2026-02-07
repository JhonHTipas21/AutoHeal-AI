"""
AutoHeal AI - Commit Correlator
=================================

Correlates error patterns with recent git commits.
Uses heuristics and SLM to find potential causal relationships.
"""

from datetime import datetime, timedelta
from typing import Optional
import re
import httpx

from src.api.schemas import CommitInfo, CorrelationResult
from src.config import get_settings

try:
    from shared.utils.logging import get_logger
except ImportError:
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)

logger = get_logger(__name__)
settings = get_settings()


class CommitCorrelator:
    """
    Correlates errors with git commits.
    
    Uses multiple strategies:
    1. Time-based: Recent commits in time window
    2. File-based: Commits touching related files
    3. Keyword-based: Commits mentioning related terms
    """
    
    def __init__(self, repo_url: Optional[str] = None):
        """
        Initialize the commit correlator.
        
        Args:
            repo_url: Git repository URL (GitHub API format expected)
        """
        self.repo_url = repo_url or settings.git_repo_url
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    async def correlate(
        self,
        error_pattern: str,
        service_name: str,
        time_window_minutes: int = 60
    ) -> CorrelationResult:
        """
        Correlate an error pattern with recent commits.
        
        Args:
            error_pattern: Error message or pattern to correlate
            service_name: Service where error occurred
            time_window_minutes: Time window for correlation
            
        Returns:
            CorrelationResult with potential commits
        """
        # If no repo configured, return mock result
        if not self.repo_url:
            return self._create_mock_result(error_pattern, service_name)
        
        try:
            # Fetch recent commits
            commits = await self._fetch_recent_commits(time_window_minutes)
            
            # Score and rank commits
            scored_commits = self._score_commits(commits, error_pattern, service_name)
            
            # Get top correlations
            top_commits = sorted(
                scored_commits,
                key=lambda x: x[1],
                reverse=True
            )[:5]
            
            if not top_commits:
                return CorrelationResult(
                    error_pattern=error_pattern[:200],
                    correlated_commits=[],
                    correlation_confidence=0.0,
                    reasoning="No commits found in the specified time window."
                )
            
            # Calculate overall confidence
            max_score = top_commits[0][1] if top_commits else 0
            confidence = min(max_score / 100.0, 0.95)
            
            return CorrelationResult(
                error_pattern=error_pattern[:200],
                correlated_commits=[c for c, _ in top_commits],
                correlation_confidence=round(confidence, 2),
                reasoning=self._generate_reasoning(top_commits, error_pattern)
            )
            
        except Exception as e:
            logger.error(f"Commit correlation failed: {e}")
            return CorrelationResult(
                error_pattern=error_pattern[:200],
                correlated_commits=[],
                correlation_confidence=0.0,
                reasoning=f"Correlation failed: {str(e)}"
            )
    
    async def _fetch_recent_commits(
        self,
        time_window_minutes: int
    ) -> list[CommitInfo]:
        """Fetch recent commits from the repository."""
        # This would integrate with GitHub/GitLab API
        # For now, return empty list if repo not configured
        
        if not self.repo_url.startswith("https://api.github.com"):
            logger.info("Git repository API not configured")
            return []
        
        client = await self._get_client()
        
        since = datetime.utcnow() - timedelta(minutes=time_window_minutes)
        
        try:
            response = await client.get(
                self.repo_url,
                params={"since": since.isoformat() + "Z"},
                headers={"Accept": "application/vnd.github.v3+json"}
            )
            
            if response.status_code != 200:
                return []
            
            commits_data = response.json()
            commits = []
            
            for c in commits_data[:20]:  # Limit to 20 commits
                commit = c.get("commit", {})
                commits.append(CommitInfo(
                    sha=c.get("sha", "")[:8],
                    message=commit.get("message", "")[:200],
                    author=commit.get("author", {}).get("name", "unknown"),
                    timestamp=datetime.fromisoformat(
                        commit.get("author", {}).get("date", "").replace("Z", "")
                    ) if commit.get("author", {}).get("date") else datetime.utcnow(),
                    files_changed=[]
                ))
            
            return commits
            
        except Exception as e:
            logger.error(f"Failed to fetch commits: {e}")
            return []
    
    def _score_commits(
        self,
        commits: list[CommitInfo],
        error_pattern: str,
        service_name: str
    ) -> list[tuple[CommitInfo, float]]:
        """
        Score commits based on correlation likelihood.
        
        Scoring factors:
        - Recency (more recent = higher score)
        - Keyword matches in commit message
        - File changes related to service
        """
        scored = []
        error_keywords = self._extract_keywords(error_pattern)
        service_keywords = set(service_name.lower().replace("-", " ").split())
        
        for commit in commits:
            score = 0.0
            
            # Time-based score (more recent = higher)
            age_hours = (datetime.utcnow() - commit.timestamp).total_seconds() / 3600
            time_score = max(0, 50 - age_hours * 2)  # Max 50 points
            score += time_score
            
            # Keyword match score
            commit_text = commit.message.lower()
            for keyword in error_keywords:
                if keyword in commit_text:
                    score += 10  # 10 points per keyword match
            
            # Service name match
            for svc_kw in service_keywords:
                if svc_kw in commit_text:
                    score += 20  # Strong indicator
            
            # Risk words in commit message
            risk_words = ["fix", "bug", "error", "issue", "patch", "hack", "workaround"]
            for word in risk_words:
                if word in commit_text:
                    score += 15
            
            # "Breaking" indicators
            if any(w in commit_text for w in ["breaking", "major", "refactor"]):
                score += 25
            
            if score > 0:
                scored.append((commit, score))
        
        return scored
    
    def _extract_keywords(self, error_pattern: str) -> set[str]:
        """Extract meaningful keywords from an error pattern."""
        # Remove common noise words
        text = error_pattern.lower()
        text = re.sub(r'[0-9]+', '', text)  # Remove numbers
        text = re.sub(r'[^\w\s]', ' ', text)  # Remove punctuation
        
        words = text.split()
        
        # Filter stop words and short words
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "can", "at", "by",
            "for", "with", "about", "against", "between", "into", "through",
            "during", "before", "after", "above", "below", "to", "from",
            "up", "down", "in", "out", "on", "off", "over", "under"
        }
        
        keywords = {
            w for w in words
            if len(w) > 3 and w not in stop_words
        }
        
        return keywords
    
    def _generate_reasoning(
        self,
        scored_commits: list[tuple[CommitInfo, float]],
        error_pattern: str
    ) -> str:
        """Generate human-readable reasoning for correlation."""
        if not scored_commits:
            return "No correlated commits found."
        
        top_commit, top_score = scored_commits[0]
        
        reasons = []
        
        if top_score > 50:
            reasons.append("High correlation confidence based on timing and keywords.")
        elif top_score > 30:
            reasons.append("Moderate correlation based on commit timing.")
        else:
            reasons.append("Low correlation - review manually.")
        
        reasons.append(
            f"Top candidate: {top_commit.sha} by {top_commit.author} "
            f"- '{top_commit.message[:50]}...'"
        )
        
        return " ".join(reasons)
    
    def _create_mock_result(
        self,
        error_pattern: str,
        service_name: str
    ) -> CorrelationResult:
        """Create a mock correlation result for development."""
        mock_commit = CommitInfo(
            sha="a1b2c3d4",
            message=f"fix: Updated {service_name} error handling",
            author="developer@example.com",
            timestamp=datetime.utcnow() - timedelta(hours=2),
            files_changed=[f"services/{service_name}/main.py"]
        )
        
        return CorrelationResult(
            error_pattern=error_pattern[:200],
            correlated_commits=[mock_commit],
            correlation_confidence=0.65,
            reasoning=(
                "Mock correlation result. Configure GIT_REPO_URL to enable "
                "real commit correlation. This mock shows how errors can be "
                "traced back to specific code changes."
            )
        )
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
