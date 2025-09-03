"""Constants for the knowledge system."""

# Default paths
DEFAULT_PERSONAL_PATH = "/personal"
DEFAULT_MEMORY_DIR_PATH = "/personal/.internal/memory"

# Rate limiting
MIN_REQUEST_INTERVAL = 0.1  # Minimum seconds between API requests

# Search and filtering
DEFAULT_MIN_SCORE = 0.35  # Minimum relevance score for knowledge results
DEFAULT_SEARCH_LIMIT = 5  # Default number of search results
MAX_SEARCH_LIMIT = 20  # Maximum allowed search results

# Context building
DEFAULT_BUDGET_CHARS = 1200  # Default character budget for knowledge context
DEFAULT_QUERY_TRUNCATE_CHARS = 400  # Default truncation for query strings
MAX_ACTIVE_TODOS = 5  # Maximum active todos to include in context

# Timeouts
DEFAULT_REQUEST_TIMEOUT = 30.0  # Default timeout for knowledge requests

# File markers
REQUEST_END_MARKER = "<<<END_KNOWLEDGE_REQUEST>>>"
RESPONSE_COMPLETE_MARKER = "<<<KNOWLEDGE_COMPLETE>>>"

# Confidence levels
DEFAULT_CONFIDENCE = 0.8  # Default confidence for shared learnings

# Polling
RESPONSE_POLL_INTERVAL = 0.05  # Seconds between response checks