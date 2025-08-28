#!/usr/bin/env python3
"""
Text-Based Pong Game for Flynn's Arcade
A simplified terminal version of the classic Pong
"""

import sys
import os
sys.path.insert(0, '/grid/community/flynns_arcade/lib')

from kiosk_base import KioskGame
import time
import random


class TextPong(KioskGame):
    """Text-based Pong game."""
    
    def __init__(self):
        super().__init__("Text Pong", "Classic Pong in your terminal")
        self.width = 40
        self.height = 20
        self.paddle_size = 4
        self.reset_game()
        
    def reset_game(self):
        """Reset game state."""
        # Paddle positions (y coordinate)
        self.player_y = self.height // 2
        self.ai_y = self.height // 2
        
        # Ball position and velocity
        self.ball_x = self.width // 2
        self.ball_y = self.height // 2
        self.ball_vx = random.choice([-1, 1])
        self.ball_vy = random.choice([-1, 0, 1])
        
        # Scores
        self.player_score = 0
        self.ai_score = 0
        self.score = 0
        
    def render(self):
        """Render the game field."""
        # Create the game field
        field = []
        for y in range(self.height):
            row = [' '] * self.width
            
            # Draw paddles
            if abs(y - self.player_y) <= self.paddle_size // 2:
                row[1] = '|'
            if abs(y - self.ai_y) <= self.paddle_size // 2:
                row[self.width - 2] = '|'
                
            # Draw ball
            if int(self.ball_x) >= 0 and int(self.ball_x) < self.width:
                if int(self.ball_y) == y:
                    row[int(self.ball_x)] = 'O'
                    
            field.append(row)
            
        # Draw borders and field
        print("+" + "-" * self.width + "+")
        for row in field:
            print("|" + ''.join(row) + "|")
        print("+" + "-" * self.width + "+")
        
        # Display scores
        print(f"\nPlayer: {self.player_score}  |  AI: {self.ai_score}")
        print("\nControls: W/S to move, Q to quit")
        
    def process_input(self, command: str):
        """Process player input."""
        command = command.lower()
        
        if command == 'w' and self.player_y > self.paddle_size // 2:
            self.player_y -= 2
        elif command == 's' and self.player_y < self.height - self.paddle_size // 2 - 1:
            self.player_y += 2
        elif command == '':
            pass  # No input, continue game
            
        # Update game state
        self.update_ball()
        self.update_ai()
        
    def update_ball(self):
        """Update ball position."""
        # Move ball
        self.ball_x += self.ball_vx
        self.ball_y += self.ball_vy
        
        # Ball collision with top/bottom
        if self.ball_y <= 0 or self.ball_y >= self.height - 1:
            self.ball_vy = -self.ball_vy
            
        # Ball collision with paddles
        if self.ball_x <= 2:
            if abs(self.ball_y - self.player_y) <= self.paddle_size // 2 + 1:
                self.ball_vx = abs(self.ball_vx)
                self.ball_vy = random.choice([-1, 0, 1])
                self.score += 10
                self.player_score += 1
            else:
                # AI scores
                self.ai_score += 1
                self.reset_ball()
                
        elif self.ball_x >= self.width - 3:
            if abs(self.ball_y - self.ai_y) <= self.paddle_size // 2 + 1:
                self.ball_vx = -abs(self.ball_vx)
                self.ball_vy = random.choice([-1, 0, 1])
            else:
                # Player scores
                self.player_score += 1
                self.score += 50
                self.reset_ball()
                
    def reset_ball(self):
        """Reset ball to center."""
        self.ball_x = self.width // 2
        self.ball_y = self.height // 2
        self.ball_vx = random.choice([-1, 1])
        self.ball_vy = random.choice([-1, 0, 1])
        
    def update_ai(self):
        """Update AI paddle position."""
        # Simple AI: follow the ball
        if self.ball_y < self.ai_y - 1:
            self.ai_y -= 1
        elif self.ball_y > self.ai_y + 1:
            self.ai_y += 1
            
        # Keep paddle in bounds
        self.ai_y = max(self.paddle_size // 2, 
                       min(self.ai_y, self.height - self.paddle_size // 2 - 1))
                       
    def check_game_over(self) -> bool:
        """Check if game is over."""
        return self.player_score >= 5 or self.ai_score >= 5
        
    def show_instructions(self):
        """Show game instructions."""
        print("\n" + "INSTRUCTIONS".center(60))
        print("-" * 60)
        print("Use W to move paddle UP".center(60))
        print("Use S to move paddle DOWN".center(60))
        print("Press ENTER to continue game".center(60))
        print("First to 5 points wins!".center(60))
        print("Press Q to quit".center(60))


if __name__ == "__main__":
    game = TextPong()
    game.start()