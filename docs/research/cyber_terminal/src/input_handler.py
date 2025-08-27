"""
Input handling for terminal sessions.

This module provides input processing and special key handling
for sending data to terminal sessions.
"""

from typing import Dict, Optional
import logging

from .exceptions import TerminalIOError


logger = logging.getLogger(__name__)


class InputHandler:
    """Handles input processing and special key conversion."""
    
    # Special key mappings to escape sequences
    SPECIAL_KEYS = {
        # Arrow keys
        'Up': '\x1b[A',
        'Down': '\x1b[B',
        'Right': '\x1b[C',
        'Left': '\x1b[D',
        
        # Function keys
        'F1': '\x1bOP',
        'F2': '\x1bOQ',
        'F3': '\x1bOR',
        'F4': '\x1bOS',
        'F5': '\x1b[15~',
        'F6': '\x1b[17~',
        'F7': '\x1b[18~',
        'F8': '\x1b[19~',
        'F9': '\x1b[20~',
        'F10': '\x1b[21~',
        'F11': '\x1b[23~',
        'F12': '\x1b[24~',
        
        # Navigation keys
        'Home': '\x1b[H',
        'End': '\x1b[F',
        'PageUp': '\x1b[5~',
        'PageDown': '\x1b[6~',
        'Insert': '\x1b[2~',
        'Delete': '\x1b[3~',
        
        # Editing keys
        'Backspace': '\x08',
        'Tab': '\x09',
        'Enter': '\r',
        'Escape': '\x1b',
        
        # Control keys (alternative names)
        'Ctrl+A': '\x01',
        'Ctrl+B': '\x02',
        'Ctrl+C': '\x03',
        'Ctrl+D': '\x04',
        'Ctrl+E': '\x05',
        'Ctrl+F': '\x06',
        'Ctrl+G': '\x07',
        'Ctrl+H': '\x08',
        'Ctrl+I': '\x09',
        'Ctrl+J': '\x0a',
        'Ctrl+K': '\x0b',
        'Ctrl+L': '\x0c',
        'Ctrl+M': '\x0d',
        'Ctrl+N': '\x0e',
        'Ctrl+O': '\x0f',
        'Ctrl+P': '\x10',
        'Ctrl+Q': '\x11',
        'Ctrl+R': '\x12',
        'Ctrl+S': '\x13',
        'Ctrl+T': '\x14',
        'Ctrl+U': '\x15',
        'Ctrl+V': '\x16',
        'Ctrl+W': '\x17',
        'Ctrl+X': '\x18',
        'Ctrl+Y': '\x19',
        'Ctrl+Z': '\x1a',
        
        # Alt combinations (Meta key)
        'Alt+A': '\x1ba',
        'Alt+B': '\x1bb',
        'Alt+C': '\x1bc',
        'Alt+D': '\x1bd',
        'Alt+E': '\x1be',
        'Alt+F': '\x1bf',
        'Alt+G': '\x1bg',
        'Alt+H': '\x1bh',
        'Alt+I': '\x1bi',
        'Alt+J': '\x1bj',
        'Alt+K': '\x1bk',
        'Alt+L': '\x1bl',
        'Alt+M': '\x1bm',
        'Alt+N': '\x1bn',
        'Alt+O': '\x1bo',
        'Alt+P': '\x1bp',
        'Alt+Q': '\x1bq',
        'Alt+R': '\x1br',
        'Alt+S': '\x1bs',
        'Alt+T': '\x1bt',
        'Alt+U': '\x1bu',
        'Alt+V': '\x1bv',
        'Alt+W': '\x1bw',
        'Alt+X': '\x1bx',
        'Alt+Y': '\x1by',
        'Alt+Z': '\x1bz',
    }
    
    # Control character mappings
    CONTROL_CHARS = {
        'NUL': '\x00',
        'SOH': '\x01',
        'STX': '\x02',
        'ETX': '\x03',
        'EOT': '\x04',
        'ENQ': '\x05',
        'ACK': '\x06',
        'BEL': '\x07',
        'BS': '\x08',
        'HT': '\x09',
        'LF': '\x0a',
        'VT': '\x0b',
        'FF': '\x0c',
        'CR': '\x0d',
        'SO': '\x0e',
        'SI': '\x0f',
        'DLE': '\x10',
        'DC1': '\x11',
        'DC2': '\x12',
        'DC3': '\x13',
        'DC4': '\x14',
        'NAK': '\x15',
        'SYN': '\x16',
        'ETB': '\x17',
        'CAN': '\x18',
        'EM': '\x19',
        'SUB': '\x1a',
        'ESC': '\x1b',
        'FS': '\x1c',
        'GS': '\x1d',
        'RS': '\x1e',
        'US': '\x1f',
        'DEL': '\x7f',
    }
    
    def __init__(self):
        self.encoding = 'utf-8'
    
    def process_input(self, data: str, input_type: str = 'text') -> bytes:
        """
        Process input data and convert to bytes for terminal.
        
        Args:
            data: Input data string
            input_type: Type of input ('text', 'text_no_newline', 'control', 'key')
            
        Returns:
            Processed input as bytes
            
        Raises:
            ValueError: If input type is invalid or key is unknown
        """
        if input_type == 'text':
            # Regular text with automatic newline
            if not data.endswith('\n') and not data.endswith('\r'):
                data += '\n'
            return data.encode(self.encoding)
        
        elif input_type == 'text_no_newline':
            # Text without automatic newline
            return data.encode(self.encoding)
        
        elif input_type == 'control':
            # Control sequences and escape codes
            return self._process_control_input(data)
        
        elif input_type == 'key':
            # Special key names
            return self._process_key_input(data)
        
        else:
            raise ValueError(f"Invalid input type: {input_type}")
    
    def _process_control_input(self, data: str) -> bytes:
        """Process control sequences and escape codes."""
        # Handle hex escape sequences like \x03
        if '\\x' in data:
            try:
                # Replace hex escapes
                result = data.encode().decode('unicode_escape')
                return result.encode('latin1')
            except (UnicodeDecodeError, UnicodeEncodeError):
                pass
        
        # Handle octal escape sequences like \033
        if '\\' in data and any(c.isdigit() for c in data):
            try:
                result = data.encode().decode('unicode_escape')
                return result.encode('latin1')
            except (UnicodeDecodeError, UnicodeEncodeError):
                pass
        
        # Handle named control characters
        upper_data = data.upper()
        if upper_data in self.CONTROL_CHARS:
            return self.CONTROL_CHARS[upper_data].encode('latin1')
        
        # Handle Ctrl+X notation
        if data.startswith('Ctrl+') or data.startswith('CTRL+'):
            key_name = data.replace('CTRL+', 'Ctrl+')
            if key_name in self.SPECIAL_KEYS:
                return self.SPECIAL_KEYS[key_name].encode('latin1')
        
        # Handle ^X notation (caret notation)
        if data.startswith('^') and len(data) == 2:
            char = data[1].upper()
            if 'A' <= char <= 'Z':
                ctrl_code = ord(char) - ord('A') + 1
                return bytes([ctrl_code])
            elif char == '?':
                return b'\x7f'  # DEL
        
        # If no special processing, return as-is
        return data.encode(self.encoding)
    
    def _process_key_input(self, key_name: str) -> bytes:
        """Process special key names."""
        # Normalize key name
        key_name = key_name.strip()
        
        # Check direct mapping
        if key_name in self.SPECIAL_KEYS:
            return self.SPECIAL_KEYS[key_name].encode('latin1')
        
        # Check case-insensitive mapping
        for key, sequence in self.SPECIAL_KEYS.items():
            if key.lower() == key_name.lower():
                return sequence.encode('latin1')
        
        # Handle numeric function keys (F13-F24, etc.)
        if key_name.lower().startswith('f') and key_name[1:].isdigit():
            f_num = int(key_name[1:])
            if 13 <= f_num <= 24:
                # Extended function keys
                return f'\x1b[{f_num + 12}~'.encode('latin1')
        
        # Handle keypad keys
        if key_name.lower().startswith('kp_') or key_name.lower().startswith('keypad_'):
            keypad_name = key_name.lower().replace('kp_', '').replace('keypad_', '')
            keypad_mappings = {
                '0': '\x1bOp',
                '1': '\x1bOq',
                '2': '\x1bOr',
                '3': '\x1bOs',
                '4': '\x1bOt',
                '5': '\x1bOu',
                '6': '\x1bOv',
                '7': '\x1bOw',
                '8': '\x1bOx',
                '9': '\x1bOy',
                'plus': '\x1bOk',
                'minus': '\x1bOm',
                'multiply': '\x1bOj',
                'divide': '\x1bOo',
                'enter': '\x1bOM',
                'period': '\x1bOn',
                'decimal': '\x1bOn',
            }
            if keypad_name in keypad_mappings:
                return keypad_mappings[keypad_name].encode('latin1')
        
        raise ValueError(f"Unknown key name: {key_name}")
    
    def get_available_keys(self) -> Dict[str, str]:
        """Get dictionary of available special keys and their descriptions."""
        descriptions = {
            # Arrow keys
            'Up': 'Up arrow key',
            'Down': 'Down arrow key',
            'Right': 'Right arrow key',
            'Left': 'Left arrow key',
            
            # Function keys
            'F1': 'Function key F1',
            'F2': 'Function key F2',
            'F3': 'Function key F3',
            'F4': 'Function key F4',
            'F5': 'Function key F5',
            'F6': 'Function key F6',
            'F7': 'Function key F7',
            'F8': 'Function key F8',
            'F9': 'Function key F9',
            'F10': 'Function key F10',
            'F11': 'Function key F11',
            'F12': 'Function key F12',
            
            # Navigation
            'Home': 'Home key',
            'End': 'End key',
            'PageUp': 'Page Up key',
            'PageDown': 'Page Down key',
            'Insert': 'Insert key',
            'Delete': 'Delete key',
            
            # Editing
            'Backspace': 'Backspace key',
            'Tab': 'Tab key',
            'Enter': 'Enter/Return key',
            'Escape': 'Escape key',
        }
        
        # Add control key descriptions
        for key in self.SPECIAL_KEYS:
            if key.startswith('Ctrl+'):
                descriptions[key] = f"Control + {key[5:]}"
            elif key.startswith('Alt+'):
                descriptions[key] = f"Alt + {key[4:]}"
        
        return descriptions
    
    def validate_input(self, data: str, input_type: str) -> bool:
        """
        Validate input data for the specified type.
        
        Args:
            data: Input data to validate
            input_type: Type of input to validate against
            
        Returns:
            True if input is valid for the type
        """
        try:
            self.process_input(data, input_type)
            return True
        except (ValueError, UnicodeError):
            return False
    
    def get_input_examples(self) -> Dict[str, Dict[str, str]]:
        """Get examples of different input types."""
        return {
            'text': {
                'description': 'Regular text with automatic newline',
                'examples': [
                    'ls -la',
                    'echo "Hello World"',
                    'python3 script.py'
                ]
            },
            'text_no_newline': {
                'description': 'Text without automatic newline',
                'examples': [
                    'partial command',
                    'username',
                    'y'
                ]
            },
            'control': {
                'description': 'Control sequences and escape codes',
                'examples': [
                    '\\x03',  # Ctrl+C
                    '\\x1b',  # Escape
                    '^C',     # Ctrl+C (caret notation)
                    'Ctrl+Z', # Ctrl+Z
                    'ETX'     # Named control character
                ]
            },
            'key': {
                'description': 'Special key names',
                'examples': [
                    'Up',
                    'PageDown',
                    'F1',
                    'Home',
                    'Enter'
                ]
            }
        }
    
    def convert_terminalcp_input(self, data: str) -> bytes:
        """
        Convert terminalcp-style input to our format.
        
        This method provides compatibility with terminalcp input format
        where special keys use :: prefix.
        
        Args:
            data: Input data potentially containing ::KeyName sequences
            
        Returns:
            Processed input as bytes
        """
        result = b''
        i = 0
        
        while i < len(data):
            if i < len(data) - 2 and data[i:i+2] == '::':
                # Find the end of the key name
                j = i + 2
                while j < len(data) and data[j] not in ' \t\n\r':
                    j += 1
                
                key_name = data[i+2:j]
                
                try:
                    # Convert key name to escape sequence
                    key_bytes = self._process_key_input(key_name)
                    result += key_bytes
                    i = j
                except ValueError:
                    # Unknown key, treat as literal text
                    result += data[i:i+1].encode(self.encoding)
                    i += 1
            else:
                # Regular character
                result += data[i:i+1].encode(self.encoding)
                i += 1
        
        return result

