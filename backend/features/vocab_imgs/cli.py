"""
CLI Commands for Vocabulary Images management

Provides commands for:
- Seed vocabulary images from JSON files
- List loaded vocabulary images
- Clear vocabulary images

Usage:
    python -m features.vocab_imgs.cli seed-vocab-imgs
    python -m features.vocab_imgs.cli list-vocab-imgs
    python -m features.vocab_imgs.cli clear-vocab-imgs
"""
import sys
import os
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/../..')

from sqlmodel import Session, select
from db import engine
from features.vocab_imgs.models import VocabImage, VocabImageWord
from logging_client import logger


def get_data_dir() -> Path:
    """Get the data directory path for vocab images."""
    return Path(__file__).parent / "data"


def load_vocab_images_from_json():
    """Loads vocabulary images from JSON files in the data directory."""
    data_dir = get_data_dir()

    if not data_dir.exists():
        print(f"❌ Data directory not found: {data_dir}")
        return False

    json_files = list(data_dir.glob("*.json"))

    if not json_files:
        print(f"❌ No JSON files found in {data_dir}")
        return False

    with Session(engine) as session:
        try:
            loaded_count = 0

            for json_file in sorted(json_files):
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Check if vocab image already exists
                existing = session.exec(
                    select(VocabImage).where(VocabImage.id == data.get("id"))
                ).first()

                if existing:
                    print(f"⏭️  Skipping {json_file.name} - already exists (id: {data.get('id')})")
                    continue

                # Create VocabImage
                vocab_image = VocabImage(
                    id=data.get("id"),
                    name=data.get("name"),
                    description=data.get("description"),
                    cover_image=data.get("cover_image"),
                    main_image=data.get("main_image"),
                    is_active=True
                )
                session.add(vocab_image)
                session.flush()  # Ensure image is created before adding words

                # Create VocabImageWords
                words_data = data.get("words", [])
                for idx, word_data in enumerate(words_data):
                    vocab_image_word = VocabImageWord(
                        id=word_data.get("id"),
                        vocab_image_id=vocab_image.id,
                        word=word_data.get("word"),
                        definition=word_data.get("definition"),
                        category=word_data.get("category"),
                        word_order=idx + 1  # Order based on position in array
                    )
                    session.add(vocab_image_word)

                session.commit()
                loaded_count += 1
                print(f"✅ Loaded {json_file.name} ({len(words_data)} words)")

            print()
            print(f"✨ Successfully loaded {loaded_count} vocabulary theme(s)")
            return True

        except Exception as e:
            session.rollback()
            print(f"❌ Error loading vocabulary images: {e}")
            logger.error(f"Error in load_vocab_images_from_json: {e}", exc_info=True)
            return False


def list_vocab_images():
    """Lists all loaded vocabulary images."""
    with Session(engine) as session:
        try:
            vocab_images = session.exec(select(VocabImage)).all()

            if not vocab_images:
                print("⚠️  No vocabulary images found")
                return True

            print("\n" + "=" * 100)
            print("VOCABULARY IMAGES")
            print("=" * 100)

            for img in vocab_images:
                words_count = session.exec(
                    select(VocabImageWord).where(
                        VocabImageWord.vocab_image_id == img.id
                    )
                ).all()

                status = "✅ ACTIVE" if img.is_active else "❌ INACTIVE"
                print(f"\n📚 {img.name}")
                print(f"   ID: {img.id}")
                print(f"   Status: {status}")
                print(f"   Description: {img.description}")
                print(f"   Words: {len(words_count)}")
                print(f"   Created: {img.created_at.strftime('%Y-%m-%d %H:%M:%S')}")

            print("\n" + "=" * 100)
            print(f"Total: {len(vocab_images)} vocabulary theme(s)")
            print()

            return True

        except Exception as e:
            print(f"❌ Error listing vocabulary images: {e}")
            logger.error(f"Error in list_vocab_images: {e}")
            return False


def clear_vocab_images():
    """Clears all vocabulary images from the database."""
    with Session(engine) as session:
        try:
            # Delete all vocab image words first
            words = session.exec(select(VocabImageWord)).all()
            for word in words:
                session.delete(word)

            # Delete all vocab images
            images = session.exec(select(VocabImage)).all()
            for image in images:
                session.delete(image)

            session.commit()
            print(f"✅ Cleared {len(images)} vocabulary image(s) and {len(words)} word(s)")
            return True

        except Exception as e:
            session.rollback()
            print(f"❌ Error clearing vocabulary images: {e}")
            logger.error(f"Error in clear_vocab_images: {e}")
            return False


def main():
    """Main entry point for CLI."""
    if len(sys.argv) < 2:
        print_help()
        return

    command = sys.argv[1].lower()

    if command == "seed-vocab-imgs":
        load_vocab_images_from_json()

    elif command == "list-vocab-imgs":
        list_vocab_images()

    elif command == "clear-vocab-imgs":
        if len(sys.argv) < 3 or sys.argv[2].lower() != "--force":
            print("⚠️  This will delete all vocabulary images and words")
            print("   Usage: python -m features.vocab_imgs.cli clear-vocab-imgs --force")
            return
        clear_vocab_images()

    elif command in ["-h", "--help", "help"]:
        print_help()

    else:
        print(f"❌ Unknown command: {command}")
        print_help()


def print_help():
    """Prints help message."""
    print("""
╔════════════════════════════════════════════════════════════════╗
║  Vocabulary Images Manager - CLI                              ║
╚════════════════════════════════════════════════════════════════╝

AVAILABLE COMMANDS:

  seed-vocab-imgs
    Loads vocabulary images from JSON files in features/vocab_imgs/data/
    Usage: python -m features.vocab_imgs.cli seed-vocab-imgs

  list-vocab-imgs
    Lists all loaded vocabulary images and their word counts
    Usage: python -m features.vocab_imgs.cli list-vocab-imgs

  clear-vocab-imgs
    Clears all vocabulary images and words from the database
    Usage: python -m features.vocab_imgs.cli clear-vocab-imgs --force

  help, -h, --help
    Shows this help message
    Usage: python -m features.vocab_imgs.cli help

EXAMPLES:

  # Load vocabulary images from JSON
  python -m features.vocab_imgs.cli seed-vocab-imgs

  # List all loaded images
  python -m features.vocab_imgs.cli list-vocab-imgs

  # Clear all data (requires --force flag)
  python -m features.vocab_imgs.cli clear-vocab-imgs --force

═════════════════════════════════════════════════════════════════
    """)


if __name__ == "__main__":
    main()
