"""
Screen content and terminal attribute data structures.

This module defines the data structures used for representing
terminal screen content and formatting attributes.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Tuple, List, Optional
from enum import Enum


class Color(Enum):
    """Standard terminal colors."""
    BLACK = 0
    RED = 1
    GREEN = 2
    YELLOW = 3
    BLUE = 4
    MAGENTA = 5
    CYAN = 6
    WHITE = 7
    BRIGHT_BLACK = 8
    BRIGHT_RED = 9
    BRIGHT_GREEN = 10
    BRIGHT_YELLOW = 11
    BRIGHT_BLUE = 12
    BRIGHT_MAGENTA = 13
    BRIGHT_CYAN = 14
    BRIGHT_WHITE = 15


@dataclass
class TerminalAttributes:
    """Terminal character formatting attributes."""
    
    # Text formatting
    bold: bool = False
    dim: bool = False
    italic: bool = False
    underline: bool = False
    blink: bool = False
    reverse: bool = False
    strikethrough: bool = False
    
    # Colors
    foreground_color: Optional[Color] = None
    background_color: Optional[Color] = None
    
    # Extended colors (256-color mode)
    foreground_color_256: Optional[int] = None
    background_color_256: Optional[int] = None
    
    # True color (24-bit RGB)
    foreground_rgb: Optional[Tuple[int, int, int]] = None
    background_rgb: Optional[Tuple[int, int, int]] = None
    
    def reset(self):
        """Reset all attributes to default values."""
        self.bold = False
        self.dim = False
        self.italic = False
        self.underline = False
        self.blink = False
        self.reverse = False
        self.strikethrough = False
        self.foreground_color = None
        self.background_color = None
        self.foreground_color_256 = None
        self.background_color_256 = None
        self.foreground_rgb = None
        self.background_rgb = None
    
    def copy(self) -> 'TerminalAttributes':
        """Create a copy of the current attributes."""
        return TerminalAttributes(
            bold=self.bold,
            dim=self.dim,
            italic=self.italic,
            underline=self.underline,
            blink=self.blink,
            reverse=self.reverse,
            strikethrough=self.strikethrough,
            foreground_color=self.foreground_color,
            background_color=self.background_color,
            foreground_color_256=self.foreground_color_256,
            background_color_256=self.background_color_256,
            foreground_rgb=self.foreground_rgb,
            background_rgb=self.background_rgb
        )


@dataclass
class TerminalChar:
    """A single terminal character with attributes."""
    
    char: str
    attributes: TerminalAttributes = field(default_factory=TerminalAttributes)
    
    def __str__(self) -> str:
        return self.char


@dataclass
class ScreenContent:
    """Terminal screen content with metadata."""
    
    text: str
    cursor_position: Tuple[int, int]
    terminal_size: Tuple[int, int]
    timestamp: datetime
    has_more: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Optional structured content
    lines: Optional[List[str]] = None
    formatted_lines: Optional[List[List[TerminalChar]]] = None
    
    @property
    def rows(self) -> int:
        """Get number of terminal rows."""
        return self.terminal_size[0]
    
    @property
    def cols(self) -> int:
        """Get number of terminal columns."""
        return self.terminal_size[1]
    
    @property
    def cursor_row(self) -> int:
        """Get cursor row (0-based)."""
        return self.cursor_position[0]
    
    @property
    def cursor_col(self) -> int:
        """Get cursor column (0-based)."""
        return self.cursor_position[1]
    
    def get_lines(self) -> List[str]:
        """Get content as list of lines."""
        if self.lines is not None:
            return self.lines
        return self.text.split('\n')
    
    def get_line(self, line_number: int) -> str:
        """Get specific line by number (0-based)."""
        lines = self.get_lines()
        if 0 <= line_number < len(lines):
            return lines[line_number]
        return ""
    
    def get_text_at_cursor(self, length: int = 1) -> str:
        """Get text at cursor position."""
        lines = self.get_lines()
        if self.cursor_row < len(lines):
            line = lines[self.cursor_row]
            start = self.cursor_col
            end = min(start + length, len(line))
            return line[start:end]
        return ""
    
    def search_text(self, pattern: str, case_sensitive: bool = True) -> List[Tuple[int, int]]:
        """Search for text pattern and return positions."""
        positions = []
        lines = self.get_lines()
        
        search_text = pattern if case_sensitive else pattern.lower()
        
        for row, line in enumerate(lines):
            search_line = line if case_sensitive else line.lower()
            col = 0
            while True:
                pos = search_line.find(search_text, col)
                if pos == -1:
                    break
                positions.append((row, pos))
                col = pos + 1
        
        return positions
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'text': self.text,
            'cursor_position': self.cursor_position,
            'terminal_size': self.terminal_size,
            'timestamp': self.timestamp.isoformat(),
            'has_more': self.has_more,
            'metadata': self.metadata,
            'lines': self.lines
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScreenContent':
        """Create from dictionary (deserialization)."""
        return cls(
            text=data['text'],
            cursor_position=tuple(data['cursor_position']),
            terminal_size=tuple(data['terminal_size']),
            timestamp=datetime.fromisoformat(data['timestamp']),
            has_more=data.get('has_more', False),
            metadata=data.get('metadata', {}),
            lines=data.get('lines')
        )


@dataclass
class ScreenDiff:
    """Represents changes between two screen states."""
    
    added_lines: List[Tuple[int, str]]  # (line_number, content)
    removed_lines: List[int]  # line numbers
    modified_lines: List[Tuple[int, str, str]]  # (line_number, old_content, new_content)
    cursor_moved: bool
    old_cursor: Tuple[int, int]
    new_cursor: Tuple[int, int]
    
    @property
    def has_changes(self) -> bool:
        """Check if there are any changes."""
        return (len(self.added_lines) > 0 or 
                len(self.removed_lines) > 0 or 
                len(self.modified_lines) > 0 or 
                self.cursor_moved)
    
    def get_summary(self) -> str:
        """Get a human-readable summary of changes."""
        changes = []
        
        if self.added_lines:
            changes.append(f"{len(self.added_lines)} lines added")
        
        if self.removed_lines:
            changes.append(f"{len(self.removed_lines)} lines removed")
        
        if self.modified_lines:
            changes.append(f"{len(self.modified_lines)} lines modified")
        
        if self.cursor_moved:
            changes.append(f"cursor moved from {self.old_cursor} to {self.new_cursor}")
        
        if not changes:
            return "No changes"
        
        return ", ".join(changes)

