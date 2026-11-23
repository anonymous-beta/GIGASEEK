"""
Demon-themed color scheme for GIGASEEK
Professional dark aesthetic with hellfire accents
"""

from rich.console import Console
from rich.theme import Theme
from rich.panel import Panel
from rich.text import Text
from rich.align import Align

# Custom demon theme
demon_theme = Theme({
    "info": "bold cyan",
    "warning": "bold yellow",
    "error": "bold red",
    "success": "bold green",
    "demon": "bold red",
    "accent": "bold magenta",
    "dim": "dim white",
    "highlight": "bold white on red",
    "fire": "rgb(255,69,0)",
    "ember": "rgb(255,140,0)",
    "shadow": "rgb(80,80,80)",
    "blood": "rgb(139,0,0)",
    "bone": "rgb(245,245,220)",
})

console = Console(theme=demon_theme)


class DemonColors:
    """ANSI color codes for terminal output"""
    
    # Core colors
    RED = '\033[38;5;196m'
    DARK_RED = '\033[38;5;88m'
    FIRE = '\033[38;5;202m'
    EMBER = '\033[38;5;208m'
    MAGENTA = '\033[38;5;201m'
    PURPLE = '\033[38;5;93m'
    CYAN = '\033[38;5;51m'
    GREEN = '\033[38;5;82m'
    YELLOW = '\033[38;5;220m'
    GOLD = '\033[38;5;178m'
    WHITE = '\033[38;5;255m'
    BONE = '\033[38;5;230m'
    GRAY = '\033[38;5;245m'
    DARK = '\033[38;5;236m'
    BLACK = '\033[38;5;16m'
    
    # Styles
    BOLD = '\033[1m'
    DIM = '\033[2m'
    ITALIC = '\033[3m'
    UNDERLINE = '\033[4m'
    BLINK = '\033[5m'
    REVERSE = '\033[7m'
    
    # Reset
    RESET = '\033[0m'
    
    @classmethod
    def gradient(cls, text: str, start_color: tuple, end_color: tuple) -> str:
        """Apply gradient color to text"""
        result = ""
        for i, char in enumerate(text):
            ratio = i / max(len(text) - 1, 1)
            r = int(start_color[0] + (end_color[0] - start_color[0]) * ratio)
            g = int(start_color[1] + (end_color[1] - start_color[1]) * ratio)
            b = int(start_color[2] + (end_color[2] - start_color[2]) * ratio)
            result += f"\033[38;2;{r};{g};{b}m{char}"
        return result + cls.RESET
    
    @classmethod
    def fire_gradient(cls, text: str) -> str:
        """Fire gradient from dark red to bright orange"""
        return cls.gradient(text, (139, 0, 0), (255, 69, 0))
    
    @classmethod
    def hell_gradient(cls, text: str) -> str:
        """Hell gradient from purple to red"""
        return cls.gradient(text, (88, 0, 88), (255, 0, 0))
    
    @classmethod
    def demon_gradient(cls, text: str) -> str:
        """Demon gradient from black to red"""
        return cls.gradient(text, (20, 0, 0), (255, 50, 50))


def banner() -> Panel:
    """Generate the GIGASEEK banner"""
    
    banner_text = Text()
    banner_text.append("""
    ▄██████▄  ▄█     █▄  ▄██████▄   ▄████████ ▄██   ▄   ███    █▄   ▄█   ▄███████▄ 
   ███    ███ ███     ███ ███    ███ ███    ███ ███   ██▄ ███    ███ ███  ██▀     ▄██ 
   ███    █▀  ███     ███ ███    ███ ███    █▀  ███▄▄▄███ ███    ███ ███▌ ██▄   ▄██▀  
  ▄███▄▄▄    ███     ███ ███    ███ ███        ▀▀▀▀▀▀███ ███    ███ ███▌  ▀█████▀    
 ▀▀███▀▀▀    ███     ███ ███    ███ ███        ▄██   ███ ███    ███ ███  ▄██▀▀▀██▄   
   ███    █▄ ███     ███ ███    ███ ███    █▄  ███   ███ ███    ███ ███  ██▄   ▄███  
   ███    ███ ███ ▄█▌ ███ ███    ███ ███    ███ ███   ███ ███    ███ ███   ▀██████▀▀  
   ████████▀   ▀███▀   ▀▀  ▀██████▀   ████████▀   ▀█████▀  ████████▀  █▀             
    """, style="bold red")
    
    subtitle = Text()
    subtitle.append("\n  ⛧ GIGASEEK OSINT FRAMEWORK ⛧", style="bold white")
    subtitle.append("\n  Creator: ", style="dim")
    subtitle.append("Anonymous-beta", style="bold red")
    subtitle.append("\n  Version: ", style="dim")
    subtitle.append("1.0.0", style="bold cyan")
    subtitle.append("\n  \"The demon that crawls the web\"\n", style="italic dim")
    
    return Panel(
        Align.center(banner_text + subtitle),
        border_style="red",
        box=None,
        padding=(1, 2)
    )


def mini_banner() -> str:
    """Compact banner for TUI"""
    return DemonColors.fire_gradient("""
╔═╗╦╔═╗╔═╗╔═╗╔═╗╦╔═
║ ╦║║ ╦╠═╣╚═╗║╣ ║╚═
╚═╝╩╚═╝╩ ╩╚═╝╚═╝╩╚═
""") + DemonColors.GRAY + " v1.0.0 by Anonymous-beta" + DemonColors.RESET
