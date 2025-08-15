"""Token usage tracking and rate limiting for AI models.

This module tracks token usage per cyber and enforces rate limits,
especially important for subscription-based models like Cerebras.
"""

import json
from pathlib import Path
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
from threading import Lock

from mind_swarm.utils.logging import logger


@dataclass
class TokenUsage:
    """Token usage statistics for a cyber."""
    cyber_id: str
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    last_reset: datetime = field(default_factory=datetime.now)
    
    # Token bucket for rate limiting
    token_bucket: int = 0  # Current tokens available
    last_refill: datetime = field(default_factory=datetime.now)
    tokens_per_minute: int = 0  # Rate of token refill
    max_bucket_size: int = 0  # Maximum tokens that can accumulate
    
    # Per-minute tracking (rolling window) - keep for stats
    minute_window: deque = field(default_factory=lambda: deque(maxlen=60))
    
    def refill_bucket(self) -> None:
        """Refill the token bucket based on time passed."""
        if self.tokens_per_minute == 0:
            return
            
        now = datetime.now()
        time_passed = (now - self.last_refill).total_seconds() / 60.0  # In minutes
        
        if time_passed > 0:
            tokens_to_add = int(time_passed * self.tokens_per_minute)
            self.token_bucket = min(self.token_bucket + tokens_to_add, self.max_bucket_size)
            self.last_refill = now
            
            if tokens_to_add > 0:
                logger.debug(f"Refilled {tokens_to_add:,} tokens for {self.cyber_id}, "
                           f"bucket now has {self.token_bucket:,} tokens")
    
    def consume_tokens(self, tokens: int) -> bool:
        """Try to consume tokens from the bucket.
        
        Returns:
            True if tokens were available, False if not enough tokens
        """
        self.refill_bucket()
        
        if self.token_bucket >= tokens:
            self.token_bucket -= tokens
            return True
        return False
    
    def add_usage(self, input_tokens: int, output_tokens: int) -> None:
        """Add token usage."""
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_tokens += (input_tokens + output_tokens)
        
        # Add to current minute for stats
        current_minute = datetime.now().replace(second=0, microsecond=0)
        if self.minute_window and self.minute_window[-1][0] == current_minute:
            self.minute_window[-1] = (
                current_minute,
                self.minute_window[-1][1] + input_tokens + output_tokens
            )
        else:
            self.minute_window.append((current_minute, input_tokens + output_tokens))
    
    def get_tokens_per_minute(self) -> int:
        """Get tokens per minute rate based on recent usage."""
        if not self.minute_window:
            return 0
        
        now = datetime.now()
        # Look at the last 5 minutes of usage for rate calculation
        cutoff = now - timedelta(minutes=5)
        
        # Get recent entries
        recent_tokens = 0
        earliest_time = now
        for timestamp, tokens in self.minute_window:
            if timestamp >= cutoff:
                recent_tokens += tokens
                if timestamp < earliest_time:
                    earliest_time = timestamp
        
        if recent_tokens == 0:
            return 0
        
        # Calculate actual time span in minutes
        time_span = (now - earliest_time).total_seconds() / 60.0
        if time_span < 1.0:
            # If less than a minute, project to full minute rate
            if time_span > 0:
                return int(recent_tokens * (1.0 / max(0.1, time_span)))
            else:
                return recent_tokens  # If no time has passed, return tokens as-is
        else:
            # Average over actual time span
            return int(recent_tokens / time_span)
    
    def reset_daily(self) -> None:
        """Reset daily counters."""
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_tokens = 0
        self.last_reset = datetime.now()
        self.minute_window.clear()


@dataclass
class SubscriptionLimits:
    """Subscription-based token limits."""
    provider: str
    daily_tokens: int
    tokens_per_minute: int  # Calculated from daily limit
    tokens_per_cyber_per_minute: int  # Per-cyber rate limit
    
    @classmethod
    def for_cerebras(cls, active_cybers: Optional[int] = None) -> 'SubscriptionLimits':
        """Create limits for Cerebras subscription.
        
        Args:
            active_cybers: Number of currently active cybers (will be counted if not provided)
            
        Returns:
            SubscriptionLimits for Cerebras
        """
        daily_tokens = 120_000_000  # 120M tokens per day
        tokens_per_minute = daily_tokens // (24 * 60)  # ~83,333 tokens/min
        
        # Count active cybers dynamically if not provided
        if active_cybers is None:
            # Try to get active cyber count from the system
            try:
                from pathlib import Path
                import os
                # Use SUBSPACE_ROOT if set, otherwise use current directory
                subspace_root = os.getenv("SUBSPACE_ROOT", Path.cwd() / "subspace")
                cyber_dir = Path(subspace_root) / "cybers"
                
                if cyber_dir.exists():
                    # Count directories that aren't dev accounts
                    active_cybers = sum(1 for d in cyber_dir.iterdir() 
                                      if d.is_dir() and not d.name.endswith("_dev"))
                    active_cybers = max(1, active_cybers)  # At least 1
                else:
                    active_cybers = 2  # Safe default
            except:
                active_cybers = 2  # Safe default if counting fails
        
        # With huge context windows (131k), per-minute limits don't make sense
        # Instead, just ensure we don't exceed daily budget
        # Allow full minute budget per cyber since requests are naturally spaced
        tokens_per_cyber = tokens_per_minute  # 83k tokens/min when needed
        
        return cls(
            provider="cerebras",
            daily_tokens=daily_tokens,
            tokens_per_minute=tokens_per_minute,
            tokens_per_cyber_per_minute=tokens_per_cyber
        )


class TokenTracker:
    """Tracks and manages token usage across all cybers."""
    
    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize token tracker.
        
        Args:
            storage_path: Path to store token usage data
        """
        import os
        # Use SUBSPACE_ROOT if set for storage path
        if storage_path is None:
            subspace_root = os.getenv("SUBSPACE_ROOT", Path.cwd() / "subspace")
            self.storage_path = Path(subspace_root).parent / "token_usage.json"
        else:
            self.storage_path = storage_path
        self.usage: Dict[str, TokenUsage] = {}
        self.subscriptions: Dict[str, SubscriptionLimits] = {}
        self.lock = Lock()
        
        # Global daily usage by provider
        self.daily_usage: Dict[str, int] = defaultdict(int)
        self.last_daily_reset = datetime.now().date()
        
        # Initialize subscriptions
        self._init_subscriptions()
        
        # Load saved state
        self._load_state()
        
        # Check for daily reset
        self._check_daily_reset()
    
    def _init_subscriptions(self) -> None:
        """Initialize subscription limits."""
        import os
        
        # Add Cerebras if API key is present
        if os.getenv("CEREBRAS_API_KEY"):
            # Let it auto-count active cybers
            self.subscriptions["cerebras"] = SubscriptionLimits.for_cerebras()
            logger.info(f"Initialized Cerebras subscription: 120M tokens/day, "
                       f"{self.subscriptions['cerebras'].tokens_per_cyber_per_minute:,} tokens/min per cyber")
    
    def _get_or_create_usage(self, cyber_id: str, provider: str) -> TokenUsage:
        """Get or create usage tracker for a cyber."""
        if cyber_id not in self.usage:
            usage = TokenUsage(cyber_id=cyber_id)
            
            # Initialize token bucket if using subscription provider
            if provider in self.subscriptions:
                limits = self.subscriptions[provider]
                # Recalculate per-cyber rate based on current active cybers
                if provider == "cerebras":
                    limits = SubscriptionLimits.for_cerebras()
                    self.subscriptions[provider] = limits
                
                usage.tokens_per_minute = limits.tokens_per_cyber_per_minute
                # Allow accumulating up to 3 minutes worth of tokens
                usage.max_bucket_size = limits.tokens_per_cyber_per_minute * 3
                # Start with 1 minute worth of tokens
                usage.token_bucket = limits.tokens_per_cyber_per_minute
                
                logger.info(f"Initialized token bucket for {cyber_id}: "
                          f"{usage.tokens_per_minute:,} tokens/min, "
                          f"max {usage.max_bucket_size:,} tokens")
            
            self.usage[cyber_id] = usage
        
        return self.usage[cyber_id]
    
    def track_usage(
        self,
        cyber_id: str,
        provider: str,
        input_tokens: int,
        output_tokens: int
    ) -> None:
        """Track token usage for a cyber.
        
        Args:
            cyber_id: Cyber identifier
            provider: AI provider used
            input_tokens: Input/prompt tokens used
            output_tokens: Output/completion tokens generated
        """
        with self.lock:
            # Get or create usage tracker for cyber
            usage = self._get_or_create_usage(cyber_id, provider)
            
            # Track usage
            self.usage[cyber_id].add_usage(input_tokens, output_tokens)
            
            # Consume tokens from bucket if using subscription provider
            total_tokens = input_tokens + output_tokens
            if provider in self.subscriptions:
                # The tokens have already been used, so deduct them from the bucket
                # This ensures the bucket accurately reflects available tokens
                usage.token_bucket = max(0, usage.token_bucket - total_tokens)
                logger.debug(f"Consumed {total_tokens:,} tokens from {cyber_id}'s bucket, "
                           f"remaining: {usage.token_bucket:,}")
            
            # Track daily usage by provider
            self.daily_usage[provider] += total_tokens
            
            # Log if approaching limits
            self._check_limits(provider)
            
            # Save state periodically
            self._save_state()
    
    def check_rate_limit(
        self,
        cyber_id: str,
        provider: str,
        estimated_tokens: int = 1000
    ) -> Tuple[bool, Optional[str]]:
        """Check if a cyber can make an AI request.
        
        Args:
            cyber_id: Cyber identifier
            provider: AI provider to use
            estimated_tokens: Estimated tokens for the request
            
        Returns:
            Tuple of (allowed, reason_if_denied)
        """
        with self.lock:
            # Check daily reset
            self._check_daily_reset()
            
            # No limits for non-subscription providers
            if provider not in self.subscriptions:
                return True, None
            
            limits = self.subscriptions[provider]
            
            # Check daily limit first
            if self.daily_usage[provider] + estimated_tokens > limits.daily_tokens:
                remaining = limits.daily_tokens - self.daily_usage[provider]
                return False, f"Daily token limit reached for {provider} (remaining: {remaining:,})"
            
            # Get or create usage tracker
            usage = self._get_or_create_usage(cyber_id, provider)
            
            # Check token bucket
            usage.refill_bucket()
            
            if usage.token_bucket < estimated_tokens:
                # Calculate how long to wait
                tokens_needed = estimated_tokens - usage.token_bucket
                if usage.tokens_per_minute > 0:
                    minutes_to_wait = tokens_needed / usage.tokens_per_minute
                    seconds_to_wait = int(minutes_to_wait * 60)
                    wait_msg = f"Wait ~{seconds_to_wait}s for refill"
                else:
                    wait_msg = "Token refill rate not configured"
                
                return False, (f"Need {estimated_tokens:,} tokens but only have {usage.token_bucket:,}. {wait_msg}")
            
            return True, None
    
    def get_usage_stats(self, cyber_id: Optional[str] = None) -> Dict:
        """Get usage statistics.
        
        Args:
            cyber_id: Specific cyber ID or None for all
            
        Returns:
            Usage statistics dictionary
        """
        with self.lock:
            if cyber_id:
                if cyber_id not in self.usage:
                    return {"cyber_id": cyber_id, "total_tokens": 0}
                
                usage = self.usage[cyber_id]
                return {
                    "cyber_id": cyber_id,
                    "total_tokens": usage.total_tokens,
                    "input_tokens": usage.total_input_tokens,
                    "output_tokens": usage.total_output_tokens,
                    "tokens_per_minute": usage.get_tokens_per_minute(),
                    "last_reset": usage.last_reset.isoformat()
                }
            else:
                # Global stats
                stats = {
                    "daily_usage": dict(self.daily_usage),
                    "subscriptions": {},
                    "cybers": {}
                }
                
                # Add subscription info
                for provider, limits in self.subscriptions.items():
                    used = self.daily_usage.get(provider, 0)
                    stats["subscriptions"][provider] = {
                        "daily_limit": limits.daily_tokens,
                        "used_today": used,
                        "remaining": limits.daily_tokens - used,
                        "usage_percent": (used / limits.daily_tokens * 100) if limits.daily_tokens > 0 else 0
                    }
                
                # Add per-cyber stats
                for cid, usage in self.usage.items():
                    stats["cybers"][cid] = {
                        "total_tokens": usage.total_tokens,
                        "tokens_per_minute": usage.get_tokens_per_minute()
                    }
                
                return stats
    
    def _check_limits(self, provider: str) -> None:
        """Check and log if approaching limits."""
        if provider not in self.subscriptions:
            return
        
        limits = self.subscriptions[provider]
        daily_usage_pct = (self.daily_usage[provider] / limits.daily_tokens) * 100
        
        # Warn at 80%, 90%, 95%
        if daily_usage_pct >= 95 and daily_usage_pct < 96:
            logger.warning(f"⚠️ {provider} daily usage at {daily_usage_pct:.1f}% "
                          f"({self.daily_usage[provider]:,}/{limits.daily_tokens:,} tokens)")
        elif daily_usage_pct >= 90 and daily_usage_pct < 91:
            logger.warning(f"⚠️ {provider} daily usage at {daily_usage_pct:.1f}%")
        elif daily_usage_pct >= 80 and daily_usage_pct < 81:
            logger.info(f"📊 {provider} daily usage at {daily_usage_pct:.1f}%")
    
    def _check_daily_reset(self) -> None:
        """Check if we need to reset daily counters."""
        today = datetime.now().date()
        if today > self.last_daily_reset:
            logger.info(f"Resetting daily token counters for {today}")
            
            # Reset daily usage
            self.daily_usage.clear()
            
            # Reset per-cyber daily stats
            for usage in self.usage.values():
                usage.reset_daily()
            
            self.last_daily_reset = today
            self._save_state()
    
    def _save_state(self) -> None:
        """Save current state to disk."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            
            state = {
                "last_daily_reset": self.last_daily_reset.isoformat(),
                "daily_usage": dict(self.daily_usage),
                "cybers": {
                    cyber_id: {
                        "total_tokens": usage.total_tokens,
                        "input_tokens": usage.total_input_tokens,
                        "output_tokens": usage.total_output_tokens,
                        "last_reset": usage.last_reset.isoformat()
                    }
                    for cyber_id, usage in self.usage.items()
                }
            }
            
            with open(self.storage_path, 'w') as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save token tracker state: {e}")
    
    def _load_state(self) -> None:
        """Load saved state from disk."""
        if not self.storage_path.exists():
            return
        
        try:
            with open(self.storage_path, 'r') as f:
                state = json.load(f)
            
            # Load last reset date
            self.last_daily_reset = datetime.fromisoformat(state["last_daily_reset"]).date()
            
            # Load daily usage
            self.daily_usage = defaultdict(int, state.get("daily_usage", {}))
            
            # Load per-cyber usage (only if from today)
            if self.last_daily_reset == datetime.now().date():
                for cyber_id, data in state.get("cybers", {}).items():
                    usage = TokenUsage(
                        cyber_id=cyber_id,
                        total_input_tokens=data.get("input_tokens", 0),
                        total_output_tokens=data.get("output_tokens", 0),
                        total_tokens=data.get("total_tokens", 0),
                        last_reset=datetime.fromisoformat(data["last_reset"])
                    )
                    
                    # Initialize token bucket for subscription providers
                    # This ensures loaded cybers also get proper rate limiting
                    for provider, limits in self.subscriptions.items():
                        if provider == "cerebras":
                            # Recalculate limits dynamically
                            limits = SubscriptionLimits.for_cerebras()
                            self.subscriptions[provider] = limits
                            
                            usage.tokens_per_minute = limits.tokens_per_cyber_per_minute
                            usage.max_bucket_size = limits.tokens_per_cyber_per_minute * 3
                            # Start with 1 minute worth of tokens for loaded cybers
                            usage.token_bucket = limits.tokens_per_cyber_per_minute
                            usage.last_refill = datetime.now()
                            
                            logger.info(f"Initialized token bucket for loaded cyber {cyber_id}: "
                                      f"{usage.tokens_per_minute:,} tokens/min")
                            break  # Only need to configure once
                    
                    self.usage[cyber_id] = usage
            
            logger.info(f"Loaded token tracking state: {len(self.usage)} cybers, "
                       f"daily usage: {sum(self.daily_usage.values()):,} tokens")
                       
        except Exception as e:
            logger.error(f"Failed to load token tracker state: {e}")


# Global instance
token_tracker = TokenTracker()