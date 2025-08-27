"""
Terminal buffer implementation with ANSI escape sequence processing.

This module provides a virtual terminal buffer that processes ANSI escape
sequences and maintains terminal state for screen content extraction.
"""

import re
from collections import deque
from typing import List, Dict, Tuple, Optional, Deque
import logging
from datetime import datetime

from .screen_content import (
    ScreenContent, TerminalChar, TerminalAttributes, Color, ScreenDiff
)


logger = logging.getLogger(__name__)


class TerminalBuffer:
    """Virtual terminal buffer with ANSI escape sequence processing."""
    
    def __init__(self, rows: int = 24, cols: int = 80, scrollback: int = 1000):
        self.rows = rows
        self.cols = cols
        self.scrollback_limit = scrollback
        
        # Initialize screen buffer
        self.screen: List[List[TerminalChar]] = []
        self.scrollback_buffer: Deque[List[TerminalChar]] = deque(maxlen=scrollback)
        self._init_screen()
        
        # Cursor state
        self.cursor_row = 0
        self.cursor_col = 0
        self.saved_cursor = (0, 0)
        self.cursor_visible = True
        
        # Terminal attributes and state
        self.current_attrs = TerminalAttributes()
        self.tab_stops = set(range(8, cols, 8))  # Default tab stops every 8 columns
        
        # Terminal modes
        self.insert_mode = False
        self.auto_wrap = True
        self.origin_mode = False
        
        # Scroll region
        self.scroll_top = 0
        self.scroll_bottom = rows - 1
        
        # Character sets and encoding
        self.charset = 'utf-8'
        
        # ANSI escape sequence parser state
        self._escape_state = 'normal'
        self._escape_buffer = ''
        self._csi_params = []
        
        # Content change tracking
        self._last_content_hash = None
        self._content_changed = True
    
    def _init_screen(self):
        """Initialize screen buffer with empty characters."""
        self.screen = []
        for _ in range(self.rows):
            row = []
            for _ in range(self.cols):
                row.append(TerminalChar(' ', TerminalAttributes()))
            self.screen.append(row)
    
    def resize(self, rows: int, cols: int):
        """Resize terminal buffer."""
        old_rows, old_cols = self.rows, self.cols
        self.rows, self.cols = rows, cols
        
        # Adjust screen buffer
        if rows > old_rows:
            # Add new rows
            for _ in range(rows - old_rows):
                row = []
                for _ in range(cols):
                    row.append(TerminalChar(' ', TerminalAttributes()))
                self.screen.append(row)
        elif rows < old_rows:
            # Remove rows (move to scrollback if needed)
            for i in range(old_rows - 1, rows - 1, -1):
                if i < len(self.screen):
                    self.scrollback_buffer.append(self.screen[i])
                    del self.screen[i]
        
        # Adjust column width for all rows
        for row in self.screen:
            if cols > old_cols:
                # Add columns
                for _ in range(cols - old_cols):
                    row.append(TerminalChar(' ', TerminalAttributes()))
            elif cols < old_cols:
                # Remove columns
                del row[cols:]
        
        # Adjust cursor position
        self.cursor_row = min(self.cursor_row, rows - 1)
        self.cursor_col = min(self.cursor_col, cols - 1)
        
        # Adjust scroll region
        self.scroll_bottom = min(self.scroll_bottom, rows - 1)
        
        # Update tab stops
        self.tab_stops = set(range(8, cols, 8))
        
        logger.info(f"Resized terminal buffer from {old_rows}x{old_cols} to {rows}x{cols}")
    
    def process_data(self, data: bytes) -> None:
        """Process incoming terminal data and update buffer."""
        try:
            text = data.decode(self.charset, errors='replace')
        except UnicodeDecodeError:
            text = data.decode('utf-8', errors='replace')
        
        i = 0
        while i < len(text):
            char = text[i]
            
            if self._escape_state == 'normal':
                if char == '\x1b':  # ESC
                    self._escape_state = 'escape'
                    self._escape_buffer = ''
                elif char == '\r':
                    self.cursor_col = 0
                elif char == '\n':
                    self._newline()
                elif char == '\t':
                    self._tab()
                elif char == '\b':
                    self._backspace()
                elif char == '\x07':  # BEL
                    pass  # Bell - ignore for now
                elif char == '\x0e':  # SO - Shift Out
                    pass  # Character set switching - ignore for now
                elif char == '\x0f':  # SI - Shift In
                    pass  # Character set switching - ignore for now
                elif ord(char) >= 32:  # Printable character
                    self._write_char(char)
                # Ignore other control characters
            
            elif self._escape_state == 'escape':
                if char == '[':
                    self._escape_state = 'csi'
                    self._csi_params = []
                    self._escape_buffer = ''
                elif char == ']':
                    self._escape_state = 'osc'
                    self._escape_buffer = ''
                elif char in 'DEHMZ78':
                    # Single character escape sequences
                    self._process_escape_sequence(char)
                    self._escape_state = 'normal'
                else:
                    # Unknown escape sequence
                    self._escape_state = 'normal'
            
            elif self._escape_state == 'csi':
                if char.isdigit():
                    self._escape_buffer += char
                elif char == ';':
                    if self._escape_buffer:
                        self._csi_params.append(int(self._escape_buffer))
                    else:
                        self._csi_params.append(0)
                    self._escape_buffer = ''
                elif char in 'ABCDEFGHJKSTfhlmnr':
                    # CSI sequence complete
                    if self._escape_buffer:
                        self._csi_params.append(int(self._escape_buffer))
                    self._process_csi_sequence(char, self._csi_params)
                    self._escape_state = 'normal'
                else:
                    # Invalid CSI sequence
                    self._escape_state = 'normal'
            
            elif self._escape_state == 'osc':
                if char == '\x07' or char == '\x1b':  # BEL or ESC
                    # OSC sequence complete
                    self._process_osc_sequence(self._escape_buffer)
                    self._escape_state = 'normal'
                else:
                    self._escape_buffer += char
            
            i += 1
        
        self._content_changed = True
    
    def _write_char(self, char: str):
        """Write a character at the current cursor position."""
        if self.cursor_row >= self.rows:
            self.cursor_row = self.rows - 1
        
        if self.cursor_col >= self.cols:
            if self.auto_wrap:
                self._newline()
            else:
                self.cursor_col = self.cols - 1
        
        # Insert mode handling
        if self.insert_mode and self.cursor_col < self.cols - 1:
            # Shift characters to the right
            for col in range(self.cols - 1, self.cursor_col, -1):
                if col - 1 >= 0:
                    self.screen[self.cursor_row][col] = self.screen[self.cursor_row][col - 1]
        
        # Write character
        terminal_char = TerminalChar(char, self.current_attrs.copy())
        self.screen[self.cursor_row][self.cursor_col] = terminal_char
        
        # Advance cursor
        self.cursor_col += 1
    
    def _newline(self):
        """Move cursor to next line, scrolling if necessary."""
        self.cursor_row += 1
        
        if self.cursor_row > self.scroll_bottom:
            # Scroll up
            self._scroll_up(1)
            self.cursor_row = self.scroll_bottom
    
    def _tab(self):
        """Move cursor to next tab stop."""
        for tab_stop in sorted(self.tab_stops):
            if tab_stop > self.cursor_col:
                self.cursor_col = min(tab_stop, self.cols - 1)
                return
        
        # No tab stop found, move to end of line
        self.cursor_col = self.cols - 1
    
    def _backspace(self):
        """Move cursor back one position."""
        if self.cursor_col > 0:
            self.cursor_col -= 1
    
    def _scroll_up(self, lines: int):
        """Scroll screen up by specified number of lines."""
        for _ in range(lines):
            # Move top line to scrollback
            if self.scroll_top < len(self.screen):
                self.scrollback_buffer.append(self.screen[self.scroll_top])
            
            # Shift lines up
            for row in range(self.scroll_top, self.scroll_bottom):
                if row + 1 < len(self.screen):
                    self.screen[row] = self.screen[row + 1]
            
            # Clear bottom line
            if self.scroll_bottom < len(self.screen):
                self.screen[self.scroll_bottom] = [
                    TerminalChar(' ', TerminalAttributes()) for _ in range(self.cols)
                ]
    
    def _scroll_down(self, lines: int):
        """Scroll screen down by specified number of lines."""
        for _ in range(lines):
            # Shift lines down
            for row in range(self.scroll_bottom, self.scroll_top, -1):
                if row - 1 >= 0 and row < len(self.screen):
                    self.screen[row] = self.screen[row - 1]
            
            # Clear top line
            if self.scroll_top < len(self.screen):
                self.screen[self.scroll_top] = [
                    TerminalChar(' ', TerminalAttributes()) for _ in range(self.cols)
                ]
    
    def _process_escape_sequence(self, command: str):
        """Process single-character escape sequences."""
        if command == 'D':  # Index (move down)
            self.cursor_row = min(self.cursor_row + 1, self.scroll_bottom)
        elif command == 'E':  # Next line
            self._newline()
            self.cursor_col = 0
        elif command == 'H':  # Tab set
            self.tab_stops.add(self.cursor_col)
        elif command == 'M':  # Reverse index (move up)
            if self.cursor_row <= self.scroll_top:
                self._scroll_down(1)
            else:
                self.cursor_row -= 1
        elif command == 'Z':  # Identify terminal
            pass  # Would send response in real terminal
        elif command == '7':  # Save cursor
            self.saved_cursor = (self.cursor_row, self.cursor_col)
        elif command == '8':  # Restore cursor
            self.cursor_row, self.cursor_col = self.saved_cursor
    
    def _process_csi_sequence(self, command: str, params: List[int]):
        """Process CSI (Control Sequence Introducer) sequences."""
        if command == 'A':  # Cursor up
            count = params[0] if params else 1
            self.cursor_row = max(self.cursor_row - count, 0)
        
        elif command == 'B':  # Cursor down
            count = params[0] if params else 1
            self.cursor_row = min(self.cursor_row + count, self.rows - 1)
        
        elif command == 'C':  # Cursor right
            count = params[0] if params else 1
            self.cursor_col = min(self.cursor_col + count, self.cols - 1)
        
        elif command == 'D':  # Cursor left
            count = params[0] if params else 1
            self.cursor_col = max(self.cursor_col - count, 0)
        
        elif command == 'E':  # Cursor next line
            count = params[0] if params else 1
            self.cursor_row = min(self.cursor_row + count, self.rows - 1)
            self.cursor_col = 0
        
        elif command == 'F':  # Cursor previous line
            count = params[0] if params else 1
            self.cursor_row = max(self.cursor_row - count, 0)
            self.cursor_col = 0
        
        elif command == 'G':  # Cursor horizontal absolute
            col = (params[0] - 1) if params else 0
            self.cursor_col = max(0, min(col, self.cols - 1))
        
        elif command == 'H' or command == 'f':  # Cursor position
            row = (params[0] - 1) if params else 0
            col = (params[1] - 1) if len(params) > 1 else 0
            self.cursor_row = max(0, min(row, self.rows - 1))
            self.cursor_col = max(0, min(col, self.cols - 1))
        
        elif command == 'J':  # Erase in display
            mode = params[0] if params else 0
            self._erase_display(mode)
        
        elif command == 'K':  # Erase in line
            mode = params[0] if params else 0
            self._erase_line(mode)
        
        elif command == 'S':  # Scroll up
            count = params[0] if params else 1
            self._scroll_up(count)
        
        elif command == 'T':  # Scroll down
            count = params[0] if params else 1
            self._scroll_down(count)
        
        elif command == 'm':  # Select Graphic Rendition (colors/attributes)
            self._process_sgr(params)
        
        elif command == 'r':  # Set scroll region
            if len(params) >= 2:
                top = max(0, params[0] - 1)
                bottom = min(self.rows - 1, params[1] - 1)
                if top < bottom:
                    self.scroll_top = top
                    self.scroll_bottom = bottom
    
    def _process_osc_sequence(self, data: str):
        """Process OSC (Operating System Command) sequences."""
        # OSC sequences are typically for setting window title, etc.
        # We'll ignore them for now as they don't affect screen content
        pass
    
    def _erase_display(self, mode: int):
        """Erase display based on mode."""
        if mode == 0:  # Erase from cursor to end of screen
            # Clear from cursor to end of current line
            for col in range(self.cursor_col, self.cols):
                self.screen[self.cursor_row][col] = TerminalChar(' ', TerminalAttributes())
            
            # Clear all lines below cursor
            for row in range(self.cursor_row + 1, self.rows):
                for col in range(self.cols):
                    self.screen[row][col] = TerminalChar(' ', TerminalAttributes())
        
        elif mode == 1:  # Erase from beginning of screen to cursor
            # Clear all lines above cursor
            for row in range(0, self.cursor_row):
                for col in range(self.cols):
                    self.screen[row][col] = TerminalChar(' ', TerminalAttributes())
            
            # Clear from beginning of current line to cursor
            for col in range(0, self.cursor_col + 1):
                self.screen[self.cursor_row][col] = TerminalChar(' ', TerminalAttributes())
        
        elif mode == 2:  # Erase entire screen
            for row in range(self.rows):
                for col in range(self.cols):
                    self.screen[row][col] = TerminalChar(' ', TerminalAttributes())
    
    def _erase_line(self, mode: int):
        """Erase line based on mode."""
        if mode == 0:  # Erase from cursor to end of line
            for col in range(self.cursor_col, self.cols):
                self.screen[self.cursor_row][col] = TerminalChar(' ', TerminalAttributes())
        
        elif mode == 1:  # Erase from beginning of line to cursor
            for col in range(0, self.cursor_col + 1):
                self.screen[self.cursor_row][col] = TerminalChar(' ', TerminalAttributes())
        
        elif mode == 2:  # Erase entire line
            for col in range(self.cols):
                self.screen[self.cursor_row][col] = TerminalChar(' ', TerminalAttributes())
    
    def _process_sgr(self, params: List[int]):
        """Process Select Graphic Rendition (SGR) parameters."""
        if not params:
            params = [0]
        
        i = 0
        while i < len(params):
            param = params[i]
            
            if param == 0:  # Reset all attributes
                self.current_attrs.reset()
            elif param == 1:  # Bold
                self.current_attrs.bold = True
            elif param == 2:  # Dim
                self.current_attrs.dim = True
            elif param == 3:  # Italic
                self.current_attrs.italic = True
            elif param == 4:  # Underline
                self.current_attrs.underline = True
            elif param == 5:  # Blink
                self.current_attrs.blink = True
            elif param == 7:  # Reverse
                self.current_attrs.reverse = True
            elif param == 9:  # Strikethrough
                self.current_attrs.strikethrough = True
            elif param == 22:  # Normal intensity (not bold/dim)
                self.current_attrs.bold = False
                self.current_attrs.dim = False
            elif param == 23:  # Not italic
                self.current_attrs.italic = False
            elif param == 24:  # Not underlined
                self.current_attrs.underline = False
            elif param == 25:  # Not blinking
                self.current_attrs.blink = False
            elif param == 27:  # Not reversed
                self.current_attrs.reverse = False
            elif param == 29:  # Not strikethrough
                self.current_attrs.strikethrough = False
            elif 30 <= param <= 37:  # Foreground colors
                self.current_attrs.foreground_color = Color(param - 30)
            elif param == 38:  # Extended foreground color
                if i + 1 < len(params) and params[i + 1] == 5:
                    # 256-color mode
                    if i + 2 < len(params):
                        self.current_attrs.foreground_color_256 = params[i + 2]
                        i += 2
                elif i + 1 < len(params) and params[i + 1] == 2:
                    # RGB mode
                    if i + 4 < len(params):
                        r, g, b = params[i + 2], params[i + 3], params[i + 4]
                        self.current_attrs.foreground_rgb = (r, g, b)
                        i += 4
            elif param == 39:  # Default foreground color
                self.current_attrs.foreground_color = None
                self.current_attrs.foreground_color_256 = None
                self.current_attrs.foreground_rgb = None
            elif 40 <= param <= 47:  # Background colors
                self.current_attrs.background_color = Color(param - 40)
            elif param == 48:  # Extended background color
                if i + 1 < len(params) and params[i + 1] == 5:
                    # 256-color mode
                    if i + 2 < len(params):
                        self.current_attrs.background_color_256 = params[i + 2]
                        i += 2
                elif i + 1 < len(params) and params[i + 1] == 2:
                    # RGB mode
                    if i + 4 < len(params):
                        r, g, b = params[i + 2], params[i + 3], params[i + 4]
                        self.current_attrs.background_rgb = (r, g, b)
                        i += 4
            elif param == 49:  # Default background color
                self.current_attrs.background_color = None
                self.current_attrs.background_color_256 = None
                self.current_attrs.background_rgb = None
            elif 90 <= param <= 97:  # Bright foreground colors
                self.current_attrs.foreground_color = Color(param - 90 + 8)
            elif 100 <= param <= 107:  # Bright background colors
                self.current_attrs.background_color = Color(param - 100 + 8)
            
            i += 1
    
    def get_screen_content(self, format_type: str = 'text', lines: Optional[int] = None) -> ScreenContent:
        """Extract current screen content in specified format."""
        timestamp = datetime.now()
        
        if format_type == 'text':
            return self._format_as_text(lines, timestamp)
        elif format_type == 'structured':
            return self._format_as_structured(lines, timestamp)
        elif format_type == 'raw':
            return self._format_as_raw(lines, timestamp)
        elif format_type == 'ansi':
            return self._format_as_ansi(lines, timestamp)
        else:
            raise ValueError(f"Unknown format type: {format_type}")
    
    def _format_as_text(self, lines: Optional[int], timestamp: datetime) -> ScreenContent:
        """Format screen content as clean text."""
        screen_lines = []
        
        # Get screen lines
        for row in self.screen:
            line = ''.join(char.char for char in row).rstrip()
            screen_lines.append(line)
        
        # Add scrollback if requested
        if lines is None:
            # Include scrollback
            all_lines = []
            for row in self.scrollback_buffer:
                line = ''.join(char.char for char in row).rstrip()
                all_lines.append(line)
            all_lines.extend(screen_lines)
            text_lines = all_lines
        else:
            # Limit to specified number of lines
            text_lines = screen_lines[-lines:] if lines < len(screen_lines) else screen_lines
        
        # Remove trailing empty lines
        while text_lines and not text_lines[-1]:
            text_lines.pop()
        
        return ScreenContent(
            text='\n'.join(text_lines),
            cursor_position=(self.cursor_row, self.cursor_col),
            terminal_size=(self.rows, self.cols),
            timestamp=timestamp,
            has_more=len(self.scrollback_buffer) > 0,
            metadata={'format': 'text'},
            lines=text_lines
        )
    
    def _format_as_structured(self, lines: Optional[int], timestamp: datetime) -> ScreenContent:
        """Format screen content with structure information."""
        content = self._format_as_text(lines, timestamp)
        
        # Add structured metadata
        content.metadata.update({
            'format': 'structured',
            'cursor_visible': self.cursor_visible,
            'scroll_region': (self.scroll_top, self.scroll_bottom),
            'tab_stops': list(self.tab_stops),
            'terminal_modes': {
                'insert_mode': self.insert_mode,
                'auto_wrap': self.auto_wrap,
                'origin_mode': self.origin_mode
            }
        })
        
        return content
    
    def _format_as_raw(self, lines: Optional[int], timestamp: datetime) -> ScreenContent:
        """Format screen content as raw character data."""
        content = self._format_as_text(lines, timestamp)
        
        # Store formatted character data
        formatted_lines = []
        for row in self.screen:
            formatted_lines.append(row.copy())
        
        content.formatted_lines = formatted_lines
        content.metadata['format'] = 'raw'
        
        return content
    
    def _format_as_ansi(self, lines: Optional[int], timestamp: datetime) -> ScreenContent:
        """Format screen content with ANSI escape sequences preserved."""
        # This would reconstruct ANSI sequences from character attributes
        # For now, return text format with ANSI metadata
        content = self._format_as_text(lines, timestamp)
        content.metadata['format'] = 'ansi'
        
        return content
    
    def has_content_changed(self) -> bool:
        """Check if screen content has changed since last check."""
        return self._content_changed
    
    def mark_content_read(self):
        """Mark content as read (reset change flag)."""
        self._content_changed = False

