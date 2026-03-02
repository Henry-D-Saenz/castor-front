from __future__ import annotations

from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class SentimentOverview(BaseModel):
    positive: float = Field(..., ge=0.0, le=1.0)
    neutral: float = Field(..., ge=0.0, le=1.0)
    negative: float = Field(..., ge=0.0, le=1.0)


class TopicAnalysis(BaseModel):
    topic: str
    tweet_count: int = Field(..., ge=0)
    sentiment: SentimentOverview
    sample_terms: Optional[List[str]] = None
    sample_tweets_ids: Optional[List[str]] = None


class PeakEvent(BaseModel):
    timestamp: datetime
    label: Optional[str] = None
    approx_volume: int = Field(..., ge=0)


class ChartData(BaseModel):
    """
    Chart.js compatible configs.
    """
    by_topic_sentiment: Dict[str, Any]
    volume_over_time: Dict[str, Any]
    sentiment_overall: Optional[Dict[str, Any]] = None
    peaks_over_time: Optional[Dict[str, Any]] = None


class TweetData(BaseModel):
    """Tweet data for storage and display."""
    tweet_id: str = ""
    author_username: str = ""
    author_name: Optional[str] = None
    content: str = ""
    sentiment_label: Optional[str] = None
    pnd_topic: Optional[str] = None
    retweet_count: int = 0
    like_count: int = 0
    reply_count: int = 0


class CoreAnalysisResult(BaseModel):
    """
    Core analysis output shared by media and campaign products.
    """
    tweets_analyzed: int = Field(..., ge=0)
    location: str
    topic: Optional[str] = None

    time_window_from: datetime
    time_window_to: datetime

    sentiment_overview: SentimentOverview
    topics: List[TopicAnalysis]
    peaks: List[PeakEvent]
    chart_data: ChartData

    # Raw tweet data for display in frontend modals
    tweets_data: List[TweetData] = Field(default_factory=list)

    trending_topic: Optional[str] = None
    raw_query: Optional[str] = None
    narrative_metrics: Optional[Dict[str, Any]] = None  # Added for IVN and narrative indices
    from_cache: bool = False
    cached_at: Optional[datetime] = None
