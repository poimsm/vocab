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
from features.words.models import Word
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

                # Get or create VocabImage
                vocab_image = session.exec(
                    select(VocabImage).where(VocabImage.id == data.get("id"))
                ).first()

                if vocab_image:
                    # Update existing
                    vocab_image.name = data.get("name")
                    vocab_image.description = data.get("description")
                    vocab_image.cover_image = data.get("cover_image")
                    vocab_image.main_image = data.get("main_image")
                    vocab_image.is_active = True
                else:
                    # Create new
                    vocab_image = VocabImage(
                        id=data.get("id"),
                        name=data.get("name"),
                        description=data.get("description"),
                        cover_image=data.get("cover_image"),
                        main_image=data.get("main_image"),
                        is_active=True
                    )
                    session.add(vocab_image)

                session.flush()  # Ensure image is created/updated before adding words

                # Get or create VocabImageWords
                words_data = data.get("words", [])
                for idx, word_data in enumerate(words_data):
                    vocab_image_word = session.exec(
                        select(VocabImageWord).where(VocabImageWord.id == word_data.get("id"))
                    ).first()

                    if vocab_image_word:
                        # Update existing
                        vocab_image_word.vocab_image_id = vocab_image.id
                        vocab_image_word.word = word_data.get("word")
                        vocab_image_word.definition = word_data.get("definition")
                        vocab_image_word.category = word_data.get("category")
                        vocab_image_word.word_order = idx + 1
                    else:
                        # Create new
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
    """Clears unused vocabulary images from the database.

    Only deletes vocab_image_words that are NOT referenced by any word.
    Preserves vocab_image_words that are in use by existing words.
    """
    with Session(engine) as session:
        try:
            # Get all vocab_image_word IDs that are being referenced by words
            words_with_refs = session.exec(
                select(Word).where(Word.vocab_image_word_id != None)
            ).all()
            referenced_ids = {word.vocab_image_word_id for word in words_with_refs}

            # Get all vocab_image_words and identify which ones to delete
            all_vocab_image_words = session.exec(select(VocabImageWord)).all()
            words_to_delete = [w for w in all_vocab_image_words if w.id not in referenced_ids]
            words_to_keep = [w for w in all_vocab_image_words if w.id in referenced_ids]

            # Delete only unreferenced vocab_image_words
            for word in words_to_delete:
                session.delete(word)

            # Delete vocab_images that have no remaining words
            images = session.exec(select(VocabImage)).all()
            images_deleted = 0
            for image in images:
                # Check if this image has any remaining words
                remaining_words = session.exec(
                    select(VocabImageWord).where(
                        VocabImageWord.vocab_image_id == image.id
                    )
                ).all()
                if not remaining_words:
                    session.delete(image)
                    images_deleted += 1

            session.commit()

            print(f"✅ Cleared {len(words_to_delete)} unused vocab word(s)")
            print(f"✅ Preserved {len(words_to_keep)} referenced vocab word(s)")
            print(f"✅ Cleared {images_deleted} empty vocabulary image(s)")
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
