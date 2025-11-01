#!/usr/bin/env python
"""
PostgreSQL Database Restore Script

This script reads the DATABASE_URL from .env file and restores a database
from a compressed SQL backup file.
"""

import argparse
import os
import subprocess
import sys
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


def verify_backup_file(backup_path):
    """Verify that the backup file exists and is readable."""
    if not backup_path.exists():
        print(f"Error: Backup file not found: {backup_path}")
        sys.exit(1)
    
    if not backup_path.is_file():
        print(f"Error: Path is not a file: {backup_path}")
        sys.exit(1)
    
    # Check if file is compressed (ends with .gz)
    is_compressed = backup_path.suffix == ".gz" or backup_path.suffixes == [".sql", ".gz"]
    
    return is_compressed


def build_psql_command(db_config):
    """Build the psql command with appropriate connection arguments."""
    # Extract connection parameters
    host = db_config.get("HOST", "localhost")
    port = db_config.get("PORT", "5432")
    database = db_config.get("NAME")
    user = db_config.get("USER")
    password = db_config.get("PASSWORD")
    
    if not all([database, user]):
        print("Error: Missing required database connection parameters")
        sys.exit(1)
    
    # Build psql command
    cmd = [
        "psql",
        "--host", host,
        "--port", str(port),
        "--username", user,
        "--dbname", database,
        "--quiet",  # Suppress unnecessary output
        "--no-password",  # Password will be provided via PGPASSWORD env var
    ]
    
    # Set password via environment variable (more secure than command line)
    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password
    
    return cmd, env


def restore_backup(backup_path, db_config):
    """Restore the database from backup file."""
    print(f"Restoring database from backup: {backup_path}")
    print(f"Database: {db_config.get('NAME')}")
    print(f"Host: {db_config.get('HOST', 'localhost')}")
    print(f"Port: {db_config.get('PORT', '5432')}")
    
    # Confirm before proceeding
    response = input("\n⚠️  WARNING: This will overwrite the current database. Continue? (yes/no): ")
    if response.lower() not in ["yes", "y"]:
        print("Restore cancelled.")
        sys.exit(0)
    
    # Build psql command
    cmd, env = build_psql_command(db_config)
    
    print("\nRestoring database...")
    
    try:
        # Check if backup is compressed
        is_compressed = verify_backup_file(backup_path)
        
        if is_compressed:
            # Decompress and pipe to psql
            gunzip_process = subprocess.Popen(
                ["gunzip", "-c", str(backup_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            psql_process = subprocess.Popen(
                cmd,
                stdin=gunzip_process.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env
            )
            
            # Close gunzip's stdout to allow it to receive SIGPIPE if psql exits
            gunzip_process.stdout.close()
            
            # Wait for both processes to complete
            gunzip_stdout, gunzip_stderr = gunzip_process.communicate()
            psql_stdout, psql_stderr = psql_process.communicate()
            
            # Check for errors
            if gunzip_process.returncode != 0:
                error_msg = gunzip_stderr.decode() if gunzip_stderr else "Unknown error"
                print(f"\nError: Failed to decompress backup file: {error_msg}")
                sys.exit(1)
            
            if psql_process.returncode != 0:
                error_msg = psql_stderr.decode() if psql_stderr else "Unknown error"
                print(f"\nError: Database restore failed with return code {psql_process.returncode}")
                print(f"Error details: {error_msg}")
                sys.exit(1)
        else:
            # Direct restore without decompression
            with open(backup_path, "rb") as f:
                psql_process = subprocess.Popen(
                    cmd,
                    stdin=f,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env
                )
                
                psql_stdout, psql_stderr = psql_process.communicate()
                
                if psql_process.returncode != 0:
                    error_msg = psql_stderr.decode() if psql_stderr else "Unknown error"
                    print(f"\nError: Database restore failed with return code {psql_process.returncode}")
                    print(f"Error details: {error_msg}")
                    sys.exit(1)
        
        print("\n✓ Database restore completed successfully!")
        print("\nNote: You may need to run migrations if the schema has changed:")
        print("  python manage.py migrate")
        
    except FileNotFoundError:
        print("\nError: psql or gunzip command not found")
        print("Please ensure PostgreSQL client tools are installed and in your PATH")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: Failed to restore backup: {e}")
        sys.exit(1)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Restore PostgreSQL database from a backup file"
    )
    parser.add_argument(
        "backup_file",
        type=str,
        help="Path to the backup file (.sql.gz)"
    )
    
    args = parser.parse_args()
    
    # Resolve backup file path
    backup_path = Path(args.backup_file)
    if not backup_path.is_absolute():
        # If relative, resolve relative to current directory or backups directory
        if backup_path.exists():
            backup_path = backup_path.resolve()
        else:
            # Try in backups directory
            base_dir = get_base_dir()
            backup_path = (base_dir / "backups" / args.backup_file).resolve()
    
    # Verify backup file
    verify_backup_file(backup_path)
    
    # Load database configuration
    print("Loading database configuration from .env...")
    db_config = load_database_config()
    
    # Restore backup
    restore_backup(backup_path, db_config)


if __name__ == "__main__":
    main()

