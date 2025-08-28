#!/usr/bin/env python3
"""
Number Quest - A guessing game for Flynn's Arcade
Guess the number with hints and score multipliers
"""

import sys
import os
from pathlib import Path
# Add parent lib directory to path for kiosk_base import
sys.path.insert(0, str(Path(__file__).parent.parent / 'lib'))

from kiosk_base import KioskGame
import random
import time


class NumberQuest(KioskGame):
    """Number guessing game with levels and bonuses."""
    
    def __init__(self):
        super().__init__("Number Quest", "Find the hidden number!")
        self.level = 1
        self.max_number = 10
        self.attempts = 0
        self.max_attempts = 7
        self.secret_number = 0
        self.guess_history = []
        self.hints_used = 0
        self.level_score = 0
        
    def start_level(self):
        """Start a new level."""
        self.max_number = 10 * (2 ** (self.level - 1))
        self.secret_number = random.randint(1, self.max_number)
        self.attempts = 0
        self.guess_history = []
        self.hints_used = 0
        self.level_score = 1000 * self.level
        
    def render(self):
        """Render the current game state."""
        print(f"\nLEVEL {self.level}")
        print(f"Range: 1 to {self.max_number}")
        print(f"Attempts remaining: {self.max_attempts - self.attempts}")
        print(f"Level score: {self.level_score}")
        
        if self.guess_history:
            print("\nYour guesses:")
            for guess, result in self.guess_history[-5:]:  # Show last 5
                print(f"  {guess}: {result}")
                
        print("\nCommands:")
        print("  [number] - Make a guess")
        print("  H - Get a hint (-200 points)")
        print("  Q - Quit game")
        
    def process_input(self, command: str):
        """Process user input."""
        command = command.strip().upper()
        
        if command == 'H':
            self.give_hint()
        elif command.isdigit():
            self.make_guess(int(command))
        elif command != '':
            print("Invalid input! Enter a number or H for hint")
            time.sleep(1)
            
    def make_guess(self, guess: int):
        """Process a guess."""
        self.attempts += 1
        
        if guess < 1 or guess > self.max_number:
            self.guess_history.append((guess, "Out of range!"))
            self.level_score -= 50
            return
            
        if guess == self.secret_number:
            # Correct guess!
            bonus = (self.max_attempts - self.attempts) * 100
            self.score += self.level_score + bonus
            
            print("\n" + "=" * 60)
            print("CORRECT!".center(60))
            print(f"The number was {self.secret_number}".center(60))
            print(f"Level Score: {self.level_score}".center(60))
            print(f"Speed Bonus: {bonus}".center(60))
            print("=" * 60)
            
            self.wait_for_input("\nPress ENTER for next level...")
            self.level += 1
            self.start_level()
            
        elif guess < self.secret_number:
            self.guess_history.append((guess, "Too low!"))
            self.level_score -= 100
        else:
            self.guess_history.append((guess, "Too high!"))
            self.level_score -= 100
            
    def give_hint(self):
        """Give a hint about the number."""
        if self.hints_used >= 2:
            print("No more hints available this level!")
            time.sleep(1)
            return
            
        self.hints_used += 1
        self.level_score -= 200
        
        hints = []
        
        # Divisibility hints
        if self.secret_number % 2 == 0:
            hints.append("The number is EVEN")
        else:
            hints.append("The number is ODD")
            
        if self.secret_number % 3 == 0:
            hints.append("The number is divisible by 3")
            
        if self.secret_number % 5 == 0:
            hints.append("The number is divisible by 5")
            
        # Range hints
        third = self.max_number // 3
        if self.secret_number <= third:
            hints.append(f"The number is in the lower third (1-{third})")
        elif self.secret_number <= third * 2:
            hints.append(f"The number is in the middle third ({third+1}-{third*2})")
        else:
            hints.append(f"The number is in the upper third ({third*2+1}-{self.max_number})")
            
        # Give a random hint
        if hints:
            print(f"\nHINT: {random.choice(hints)}")
        else:
            # Fallback hint
            digit_sum = sum(int(d) for d in str(self.secret_number))
            print(f"\nHINT: The sum of digits is {digit_sum}")
            
        time.sleep(2)
        
    def check_game_over(self) -> bool:
        """Check if game is over."""
        if self.attempts >= self.max_attempts:
            print("\n" + "=" * 60)
            print("OUT OF ATTEMPTS!".center(60))
            print(f"The number was {self.secret_number}".center(60))
            print("=" * 60)
            time.sleep(2)
            return True
        return False
        
    def show_instructions(self):
        """Show game instructions."""
        print("\n" + "INSTRUCTIONS".center(60))
        print("-" * 60)
        print("Guess the secret number!".center(60))
        print("Each level increases the range".center(60))
        print("Fewer attempts = more points".center(60))
        print("Hints cost 200 points".center(60))
        print("Each wrong guess costs 100 points".center(60))
        
    def game_loop(self):
        """Main game loop."""
        self.start_level()
        super().game_loop()


if __name__ == "__main__":
    game = NumberQuest()
    game.start()