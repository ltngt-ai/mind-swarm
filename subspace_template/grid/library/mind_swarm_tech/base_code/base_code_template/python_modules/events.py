"""Events API for cybers to sleep efficiently and wake on events.

This module provides the Events class for managing cyber idle states,
allowing them to sleep for specified durations or until specific events
occur (like new mail arriving).

Waiting multiple times in the same script is pointless, as you need to return to the cognitive loop to think between waiting.

## Usage Examples

### Timer Sleep
```python
# Sleep for 30 seconds
events.sleep(30)
print("Woke up after 30 seconds")

# Sleep for 5 minutes
events.sleep(300)
```

### Wake on New Mail
```python
# Sleep until new mail arrives (max 60 seconds)
new_mail = events.wait_for_mail(timeout=60)
if new_mail:
    print(f"New mail arrived: {new_mail}")
else:
    print("No mail received within timeout")
```

### Efficient Idle with Mail Check
```python
# Sleep for 30 seconds but wake early if mail arrives
new_mail = events.wait_for_mail(30)
if new_mail:
    print(f"New mail arrived: {new_mail}")
else:
    print("Completed sleep duration without mail")
```

## Important Notes

1. **Sleep durations are in seconds**
2. **Maximum sleep duration is 300 seconds (5 minutes) for safety**
3. **Mail wake events check the inbox directory for new messages**
4. **Sleep can be interrupted by shutdown signals**
5. **Only wait ONCE per script** - Multiple waits are ineffective. Return to cognitive loop between waits.

## Why Only One Wait?

Python scripts run within a single cognitive cycle. The cyber cannot think or process
information until the script completes and returns to the cognitive loop. Multiple
waits just delay without allowing thought.

**WRONG - Multiple waits in one script:**
```python
# This doesn't work as expected!
events.sleep(10)
print("First wait done")  # Cyber hasn't thought about this yet
events.sleep(10)  # WARNING will be printed!
print("Second wait done")  # Still no thinking happened
```

**RIGHT - Let cognitive loop handle multiple waits:**
```python
# In one execution:
new_mail = events.wait_for_mail(30)
if new_mail:
    memory.add("mail_received", True)
# Script ends, cyber thinks, decides next action

# In next execution (if cyber decides to wait again):
if memory.get("mail_received"):
    # Process the mail...
else:
    # Wait again or do something else
```
"""

import time
from pathlib import Path
from typing import Dict, Any, Optional, List


class EventsError(Exception):
    """Base exception for events operations."""
    pass


class Events:
    """Main events interface for efficient cyber idling.
    
    The Events class provides methods to sleep for specified durations
    or until specific events occur, allowing cybers to idle efficiently
    without consuming resources.
    
    Examples:
        ```python
        # The events object is pre-initialized for you
        
        # Sleep for 30 seconds
        events.sleep(30)
        
        # Wait for new mail
        new_mail = events.wait_for_mail(timeout=60)
        
        # Sleep or wake on mail
        reason = events.sleep_or_mail(30)
        ```
    """
    
    def __init__(self, context: Dict[str, Any]):
        """Initialize the events system.
        
        Args:
            context: Cyber context containing personal_dir and other info
        """
        self.context = context
        self.personal_dir = Path(context.get("personal_dir", "/personal"))
        self.inbox_dir = self.personal_dir / "inbox"
        self.shutdown_file = self.personal_dir / ".internal" / "shutdown"
        
        # Track mail state
        self._last_mail_check = None
        self._known_mail_files = set()
        self._update_known_mail()
        
        # Track if we've already waited in this script execution
        self._has_waited = False
    
    def _update_known_mail(self):
        """Update the set of known mail files."""
        try:
            if self.inbox_dir.exists():
                self._known_mail_files = set(f.name for f in self.inbox_dir.iterdir() 
                                            if f.is_file() and f.suffix in ['.msg', '.json'])
            else:
                self._known_mail_files = set()
            self._last_mail_check = time.time()
        except Exception as e:
            # Ignore errors reading inbox
            self._known_mail_files = set()
    
    def _check_for_new_mail(self) -> List[str]:
        """Check if new mail has arrived since last check.
        
        Returns:
            List of new mail file names
        """
        try:
            if not self.inbox_dir.exists():
                return []
            
            current_files = set(f.name for f in self.inbox_dir.iterdir() 
                              if f.is_file() and f.suffix in ['.msg', '.json'])
            
            new_files = current_files - self._known_mail_files
            
            # Update known files if there are new ones
            if new_files:
                self._known_mail_files = current_files
                self._last_mail_check = time.time()
            
            return list(new_files)
        except Exception:
            return []
    
    def _check_shutdown(self) -> bool:
        """Check if shutdown has been requested.
        
        Returns:
            True if shutdown file exists
        """
        try:
            return self.shutdown_file.exists()
        except Exception:
            return False
    
    def sleep(self, duration: float) -> str:
        """Sleep for a specified duration.
        
        This method causes the cyber to sleep for the specified number of seconds,
        efficiently idling without consuming CPU resources. The sleep can be
        interrupted by a shutdown signal.
        
        Args:
            duration: Number of seconds to sleep (max 300)
            
        Returns:
            "completed" if full duration elapsed, "shutdown" if interrupted
            
        Raises:
            EventsError: If duration is invalid
            
        Examples:
            ```python
            # Sleep for 30 seconds
            result = events.sleep(30)
            if result == "shutdown":
                print("Sleep interrupted by shutdown")
            ```
        """
        # Check if we've already waited in this script
        if self._has_waited:
            print("⚠️ WARNING: Multiple waits in a single script detected!")
            print("   Waiting multiple times in one script is ineffective.")
            print("   Return to the cognitive loop to think between waits.")
            print("   Consider using a longer single wait instead.")
        self._has_waited = True
        
        if duration <= 0:
            raise EventsError("Sleep duration must be positive")
        
        if duration > 300:
            raise EventsError("Maximum sleep duration is 300 seconds (5 minutes)")
        
        start_time = time.time()
        check_interval = 0.5  # Check for shutdown every 500ms
        
        while time.time() - start_time < duration:
            # Check for shutdown
            if self._check_shutdown():
                return "shutdown"
            
            # Sleep for interval or remaining time, whichever is shorter
            remaining = duration - (time.time() - start_time)
            sleep_time = min(check_interval, remaining)
            
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        return "completed"
    
    def wait_for_mail(self, timeout: float = 60) -> Optional[List[str]]:
        """Wait for new mail to arrive.
        
        This method causes the cyber to sleep until new mail arrives in the inbox,
        or until the timeout expires. Checks for new mail every second.
        
        Args:
            timeout: Maximum seconds to wait (default 60, max 300)
            
        Returns:
            List of new mail file names if mail arrived, None if timeout
            
        Raises:
            EventsError: If timeout is invalid
            
        Examples:
            ```python
            # Wait up to 60 seconds for mail
            new_mail = events.wait_for_mail(60)
            if new_mail:
                print(f"Got {len(new_mail)} new messages")
                for mail in new_mail:
                    print(f"  - {mail}")
            ```
        """
        # Check if we've already waited in this script
        if self._has_waited:
            print("⚠️ WARNING: Multiple waits in a single script detected!")
            print("   Waiting multiple times in one script is ineffective.")
            print("   Return to the cognitive loop to think between waits.")
            print("   Consider using a longer single wait instead.")
        self._has_waited = True
        
        if timeout <= 0:
            raise EventsError("Timeout must be positive")
        
        if timeout > 300:
            raise EventsError("Maximum timeout is 300 seconds (5 minutes)")
        
        start_time = time.time()
        check_interval = 1.0  # Check for mail every second
        
        # Update baseline of known mail
        self._update_known_mail()
        
        while time.time() - start_time < timeout:
            # Check for shutdown
            if self._check_shutdown():
                return None
            
            # Check for new mail
            new_mail = self._check_for_new_mail()
            if new_mail:
                return new_mail
            
            # Sleep for interval or remaining time
            remaining = timeout - (time.time() - start_time)
            sleep_time = min(check_interval, remaining)
            
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        return None
    
    def get_idle_duration(self) -> float:
        """Get recommended idle sleep duration based on context.
        
        Returns a suggested sleep duration based on recent activity patterns.
        Starts with short sleeps and gradually increases for efficiency.
        
        Returns:
            Recommended sleep duration in seconds
            
        Examples:
            ```python
            # Get smart idle duration
            duration = events.get_idle_duration()
            print(f"Sleeping for {duration} seconds")
            events.sleep(duration)
            ```
        """
        # Could be enhanced to track activity patterns
        # For now, return a reasonable default
        return 10.0  # 10 seconds is a good balance