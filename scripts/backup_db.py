#!/usr/bin/env python
"""
PostgreSQL Database Backup Script

This script reads the DATABASE_URL from .env file and creates a compressed
SQL backup of the PostgreSQL database using pg_dump.
"""

import gzip
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv


def get_base_dir():
    """Get the project base directory."""
    return Path(__file__).resolve().parent.parent


def load_database_config():
    """Load and parse DATABASE_URL from .env file."""
    base_dir = get_base_dir()
    env_path = base_dir / ".env"
    
    if not env_path.exists():
        print(f"Error: .env file not found at {env_path}")
        sys.exit(1)
    
    # Load environment variables (override=True to ensure .env values are used)
    load_dotenv(env_path, override=True)
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print(f"Error: DATABASE_URL not found in .env file at {env_path}")
        print("Please ensure DATABASE_URL is set in your .env file")
        sys.exit(1)
    
    # Parse the database URL
    try:
        db_config = dj_database_url.parse(database_url)
    except Exception as e:
        print(f"Error: Failed to parse DATABASE_URL: {e}")
        sys.exit(1)
    
    # Check if it's PostgreSQL
    if db_config.get("ENGINE") != "django.db.backends.postgresql":
        print("Error: DATABASE_URL does not point to a PostgreSQL database")
        print(f"Current database engine: {db_config.get('ENGINE')}")
        sys.exit(1)
    
    return db_config


def create_backup_directory():
    """Create backups directory if it doesn't exist."""
    base_dir = get_base_dir()
    backups_dir = base_dir / "backups"
    backups_dir.mkdir(exist_ok=True)
    return backups_dir


def generate_backup_filename():
    """Generate a timestamped backup filename."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"backup_{timestamp}.sql.gz"


def get_connection_string(db_config):
    """Build PostgreSQL connection string."""
    host = db_config.get("HOST", "localhost")
    port = db_config.get("PORT", "5432")
    database = db_config.get("NAME")
    user = db_config.get("USER")
    password = db_config.get("PASSWORD", "")
    
    if not all([database, user]):
        print("Error: Missing required database connection parameters")
        sys.exit(1)
    
    # Build connection string
    conn_string = f"host={host} port={port} dbname={database} user={user}"
    if password:
        conn_string += f" password={password}"
    
    return conn_string


def dump_database(conn_string, output_file):
    """Dump the database to a file using pg_dump."""
    import subprocess
    
    # Try to find pg_dump
    result = subprocess.run(
        ["which", "pg_dump"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print("\nError: pg_dump command not found")
        print("\nPlease install PostgreSQL client tools:")
        print("  sudo apt-get update")
        print("  sudo apt-get install postgresql-client")
        print("\nOr on macOS:")
        print("  brew install postgresql")
        print("\nAfter installation, run this script again.")
        sys.exit(1)
    
    pg_dump_cmd = result.stdout.strip()
    return dump_with_pg_dump(conn_string, output_file, pg_dump_cmd)


def dump_with_pg_dump(conn_string, output_file, pg_dump_cmd):
    """Use pg_dump command for backup."""
    import subprocess
    
    # Parse connection string to extract parameters
    params = {}
    for part in conn_string.split():
        if "=" in part:
            key, value = part.split("=", 1)
            params[key] = value
    
    # Build pg_dump command
    cmd = [
        pg_dump_cmd,
        "--host", params.get("host", "localhost"),
        "--port", params.get("port", "5432"),
        "--username", params.get("user"),
        "--dbname", params.get("dbname"),
        "--clean",
        "--if-exists",
        "--create",
        "--verbose",
        "--no-password",
    ]
    
    env = os.environ.copy()
    if "password" in params:
        env["PGPASSWORD"] = params["password"]
    
    # Run pg_dump and compress
    with gzip.open(output_file, "wb") as gz_file:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            
            # Check for version mismatch error
            if "version mismatch" in error_msg.lower() or "aborting because of server version" in error_msg.lower():
                print("\n⚠️  Version mismatch detected!")
                print("\nYour PostgreSQL client version doesn't match the server version.")
                print("\nTo fix this, install PostgreSQL 16 client tools:")
                print("\nFor Ubuntu/Debian:")
                print("  sudo apt-get update")
                print("  sudo apt-get install -y postgresql-client-16")
                print("\nOr install from PostgreSQL official repository:")
                print("  sudo sh -c 'echo \"deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main\" > /etc/apt/sources.list.d/pgdg.list'")
                print("  wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -")
                print("  sudo apt-get update")
                print("  sudo apt-get install -y postgresql-client-16")
                print("\nAlternatively, you can try using --no-version-check flag")
                print("(but this may cause compatibility issues)")
            
            raise Exception(f"pg_dump failed: {error_msg}")
        
        gz_file.write(stdout)
    
    return True




def create_backup():
    """Main function to create the database backup."""
    print("Starting database backup...")
    
    # Load database configuration
    print("Loading database configuration from .env...")
    db_config = load_database_config()
    print(f"Database: {db_config.get('NAME')}")
    print(f"Host: {db_config.get('HOST', 'localhost')}")
    print(f"Port: {db_config.get('PORT', '5432')}")
    
    # Create backups directory
    backups_dir = create_backup_directory()
    print(f"Backups directory: {backups_dir}")
    
    # Generate backup filename
    backup_filename = generate_backup_filename()
    backup_path = backups_dir / backup_filename
    print(f"Backup file: {backup_path}")
    
    # Get connection string
    conn_string = get_connection_string(db_config)
    
    # Create backup
    print("\nCreating backup...")
    try:
        dump_database(conn_string, backup_path)
        
        # Get file size
        file_size = backup_path.stat().st_size
        file_size_mb = file_size / (1024 * 1024)
        
        print(f"\n✓ Backup completed successfully!")
        print(f"  File: {backup_path}")
        print(f"  Size: {file_size_mb:.2f} MB")
        print(f"\nTo restore this backup, run:")
        print(f"  uv run python scripts/restore_db.py {backup_path}")
        
    except Exception as e:
        print(f"\nError: Failed to create backup: {e}")
        # Clean up partial backup file if it exists
        if backup_path.exists():
            backup_path.unlink()
        sys.exit(1)


if __name__ == "__main__":
    create_backup()
