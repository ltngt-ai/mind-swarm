#!/usr/bin/env python3
"""
Flynn's Arcade Main Menu
The entry point for all arcade games
"""

import sys
import os
import subprocess
import time
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent / 'lib'))

from kiosk_base import TerminalAPI


class ArcadeMenu:
    """Main arcade menu system."""
    
    def __init__(self):
        self.games = self.discover_games()
        self.running = True
        
    def discover_games(self):
        """Discover available games."""
        games = []
        games_dir = Path(__file__).parent / 'games'
        
        if games_dir.exists():
            for game_file in games_dir.glob('*.py'):
                # Read first few lines to get description
                description = "A classic arcade game"
                try:
                    with open(game_file, 'r') as f:
                        lines = f.readlines()[:10]
                        for line in lines:
                            if line.strip().startswith('"""') and len(line.strip()) > 3:
                                description = line.strip()[3:]
                                break
                            elif not line.startswith('#') and not line.startswith('"""'):
                                break
                except:
                    pass
                    
                games.append({
                    'name': game_file.stem.replace('_', ' ').title(),
                    'file': str(game_file),
                    'description': description
                })
                
        return sorted(games, key=lambda x: x['name'])
        
    def display_header(self):
        """Display arcade header."""
        TerminalAPI.clear()
        print("=" * 60)
        print(r"""
    _____ _     _   _ _   _ _   _ _ ____  
   |  ___| |   | | | | \ | | \ | ( ) ___|
   | |_  | |   | |_| |  \| |  \| |/\___ \ 
   |  _| | |___|  _  | |\  | |\  |  ___) |
   |_|   |_____|_| |_|_| \_|_| \_| |____/ 
                                           
       ___  ____   ____    _    ____  _____ 
      / _ \|  _ \ / ___|  / \  |  _ \| ____|
     | |_| | |_) | |     / _ \ | | | |  _|  
     |  _  |  _ <| |___ / ___ \| |_| | |___ 
     |_| |_|_| \_\\____/_/   \_\____/|_____|
        """.center(60))
        print("=" * 60)
        print("Where Digital Dreams Come To Play".center(60))
        print("=" * 60)
        
    def display_menu(self):
        """Display game menu."""
        print("\n" + "AVAILABLE GAMES".center(60))
        print("-" * 60)
        
        if not self.games:
            print("No games found! Check the games directory.".center(60))
        else:
            for i, game in enumerate(self.games, 1):
                print(f"\n  [{i}] {game['name']}")
                print(f"      {game['description']}")
                
        print("\n" + "-" * 60)
        print("[Q] Exit Arcade".center(60))
        print("-" * 60)
        
    def run_game(self, game):
        """Run a selected game."""
        print(f"\nLaunching {game['name']}...")
        time.sleep(1)
        
        try:
            # Run the game as a subprocess
            result = subprocess.run([sys.executable, game['file']], 
                                  capture_output=False)
            if result.returncode != 0:
                print(f"Game crashed with code {result.returncode}")
        except KeyboardInterrupt:
            print("\nReturning to arcade...")
        except Exception as e:
            print(f"Error running game: {e}")
            
        print("\nPress ENTER to continue...")
        input()
        
    def run(self):
        """Run the arcade menu."""
        while self.running:
            self.display_header()
            self.display_menu()
            
            choice = input("\nSelect a game > ").strip().upper()
            
            if choice == 'Q':
                self.running = False
                print("\nThanks for visiting Flynn's Arcade!")
                print("Come back soon!")
                time.sleep(2)
                
            elif choice.isdigit():
                game_num = int(choice) - 1
                if 0 <= game_num < len(self.games):
                    self.run_game(self.games[game_num])
                else:
                    print("Invalid selection!")
                    time.sleep(1)
            else:
                print("Invalid choice!")
                time.sleep(1)


def main():
    """Main entry point."""
    arcade = ArcadeMenu()
    try:
        arcade.run()
    except KeyboardInterrupt:
        print("\n\nArcade shutting down...")
    except Exception as e:
        print(f"Arcade error: {e}")
        

if __name__ == "__main__":
    main()