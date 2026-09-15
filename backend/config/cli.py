"""
CLI Commands for global configuration management

Provides commands for:
- Load global configuration
- View global configuration
- Update configuration
- Reload cache

Usage:
    python -m config.cli load-global-config
    python -m config.cli show-config
    python -m config.cli reload-cache
    python -m config.cli set-config MAX_USERS 2000
"""
import sys
import os
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

from sqlmodel import Session
from db import engine
from config.global_config import GlobalConfigManager
from logging_client import logger


def load_global_config():
    """Loads initial global configurations in the DB."""
    from seeds.seed_global_config import seed_global_config

    with Session(engine) as session:
        try:
            seed_global_config(session)
            print("✅ Global configurations loaded successfully")
            return True
        except Exception as e:
            print(f"❌ Error loading configurations: {e}")
            logger.error(f"Error in load_global_config: {e}")
            return False


def show_config():
    """Shows all current global configurations."""
    with Session(engine) as session:
        try:
            configs = GlobalConfigManager.get_all(session)

            if not configs:
                print("⚠️ No configurations loaded")
                return True

            print("\n" + "=" * 80)
            print("GLOBAL CONFIGURATIONS")
            print("=" * 80)

            for key, value in sorted(configs.items()):
                print(f"{key:<40} = {value}")

            print("=" * 80)
            print(f"Total: {len(configs)} configurations")
            print()

            return True
        except Exception as e:
            print(f"❌ Error showing configurations: {e}")
            logger.error(f"Error in show_config: {e}")
            return False


def set_config(key: str, value: str):
    """Updates a specific configuration."""
    if not key or not value:
        print("❌ Usage: set-config <KEY> <VALUE>")
        return False

    with Session(engine) as session:
        try:
            config = GlobalConfigManager.set(session, key, value)
            print(f"✅ Configuration updated:")
            print(f"   {key} = {value}")
            print(f"   Updated: {config.updated_at}")
            return True
        except Exception as e:
            print(f"❌ Error updating configuration: {e}")
            logger.error(f"Error in set_config: {e}")
            return False


def reload_cache():
    """Reloads the cache of global configurations."""
    with Session(engine) as session:
        try:
            GlobalConfigManager.clear_cache()
            GlobalConfigManager.load_cache(session)
            print("✅ Configuration cache reloaded successfully")
            return True
        except Exception as e:
            print(f"❌ Error reloading cache: {e}")
            logger.error(f"Error in reload_cache: {e}")
            return False


def main():
    """Main entry point for CLI."""
    if len(sys.argv) < 2:
        print_help()
        return

    command = sys.argv[1].lower()

    if command == "load-global-config":
        load_global_config()

    elif command == "show-config":
        show_config()

    elif command == "reload-cache":
        reload_cache()

    elif command == "set-config":
        if len(sys.argv) < 4:
            print("❌ Usage: set-config <KEY> <VALUE>")
            return
        key = sys.argv[2]
        value = sys.argv[3]
        set_config(key, value)

    elif command in ["-h", "--help", "help"]:
        print_help()

    else:
        print(f"❌ Unknown command: {command}")
        print_help()


def print_help():
    """Prints help message."""
    print("""
╔════════════════════════════════════════════════════════════════╗
║  Global Configuration Manager - CLI                           ║
╚════════════════════════════════════════════════════════════════╝

AVAILABLE COMMANDS:

  load-global-config
    Loads initial global configurations in the DB
    Usage: python -m config.cli load-global-config

  show-config
    Shows all current global configurations
    Usage: python -m config.cli show-config

  set-config <KEY> <VALUE>
    Updates a specific configuration
    Usage: python -m config.cli set-config MAX_USERS 2000

  reload-cache
    Reloads the configuration cache in memory
    Usage: python -m config.cli reload-cache

  help, -h, --help
    Shows this help message
    Usage: python -m config.cli help

EXAMPLES:

  # Load initial configuration
  python -m config.cli load-global-config

  # Show all configurations
  python -m config.cli show-config

  # Change user limit to 5000
  python -m config.cli set-config MAX_USERS 5000

  # Change words limit to 1000
  python -m config.cli set-config MAX_WORDS_PER_USER 1000

  # Reload cache
  python -m config.cli reload-cache

═════════════════════════════════════════════════════════════════
    """)


if __name__ == "__main__":
    main()
