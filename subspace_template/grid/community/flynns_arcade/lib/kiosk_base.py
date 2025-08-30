#!/usr/bin/env python3
"""
Flynn's Arcade Kiosk Base Framework
A base class for terminal-based games that can run via the terminal API
"""

import json
import time
import sys
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pathlib import Path


class KioskGame(ABC):
    """Base class for arcade games running as kiosks."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.running = False
        self.score = 0
        self.high_scores_file = Path(f"/grid/community/flynns_arcade/high_scores_{name.lower().replace(' ', '_')}.json")
        self.state: Dict[str, Any] = {}
        
    def start(self):
        """Start the game kiosk."""
        self.running = True
        self.clear_screen()
        self.display_header()
        self.show_instructions()
        self.wait_for_input("\nPress ENTER to start...")
        self.game_loop()
        
    def game_loop(self):
        """Main game loop."""
        while self.running:
            self.clear_screen()
            self.display_header()
            self.render()
            
            command = self.get_input()
            if command.lower() == 'q':
                self.quit()
            else:
                self.process_input(command)
                
            if self.check_game_over():
                self.handle_game_over()
                break
                
    @abstractmethod
    def render(self):
        """Render the current game state."""
        pass
        
    @abstractmethod
    def process_input(self, command: str):
        """Process user input."""
        pass
        
    @abstractmethod
    def check_game_over(self) -> bool:
        """Check if the game is over."""
        pass
        
    @abstractmethod
    def show_instructions(self):
        """Display game instructions."""
        pass
        
    def display_header(self):
        """Display the game header."""
        print("=" * 60)
        print(f"  FLYNN'S ARCADE - {self.name.upper()}  ".center(60))
        print("=" * 60)
        print(f"Score: {self.score}".center(60))
        print("-" * 60)
        
    def clear_screen(self):
        """Clear the terminal screen."""
        print("\033[2J\033[H")  # ANSI escape codes for clear
        
    def get_input(self, prompt: str = "> ") -> str:
        """Get input from the user."""
        try:
            return input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            self.quit()
            return ""
            
    def wait_for_input(self, message: str = "Press ENTER to continue..."):
        """Wait for user to press enter."""
        input(message)
        
    def quit(self):
        """Quit the game."""
        self.running = False
        self.save_high_score()
        print("\n\nThanks for playing!")
        print("Returning to the arcade...")
        time.sleep(2)
        
    def handle_game_over(self):
        """Handle game over."""
        print("\n" + "=" * 60)
        print("GAME OVER".center(60))
        print(f"Final Score: {self.score}".center(60))
        print("=" * 60)
        self.save_high_score()
        self.show_high_scores()
        self.wait_for_input("\nPress ENTER to return to the arcade...")
        
    def save_high_score(self):
        """Save high score."""
        high_scores = self.load_high_scores()
        
        # Add current score
        high_scores.append({
            "score": self.score,
            "timestamp": time.time(),
            "player": "PLAYER"  # Could be extended to track cyber names
        })
        
        # Keep top 10 scores
        high_scores.sort(key=lambda x: x["score"], reverse=True)
        high_scores = high_scores[:10]
        
        # Save to file
        try:
            self.high_scores_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.high_scores_file, 'w') as f:
                json.dump(high_scores, f, indent=2)
        except Exception as e:
            print(f"Could not save high scores: {e}")
            
    def load_high_scores(self) -> List[Dict]:
        """Load high scores."""
        try:
            if self.high_scores_file.exists():
                with open(self.high_scores_file, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return []
        
    def show_high_scores(self):
        """Display high scores."""
        scores = self.load_high_scores()
        if scores:
            print("\n" + "HIGH SCORES".center(60))
            print("-" * 60)
            for i, entry in enumerate(scores[:5], 1):
                score_str = f"{i}. {entry['player']}: {entry['score']}"
                print(score_str.center(60))


class TerminalAPI:
    """API for terminal-based interaction with cybers."""
    
    @staticmethod
    def send_output(text: str):
        """Send output to terminal."""
        print(text)
        
    @staticmethod
    def get_input(prompt: str = "") -> str:
        """Get input from terminal."""
        return input(prompt)
        
    @staticmethod
    def clear():
        """Clear terminal."""
        print("\033[2J\033[H")
        
    @staticmethod
    def set_cursor(row: int, col: int):
        """Set cursor position."""
        print(f"\033[{row};{col}H", end="")