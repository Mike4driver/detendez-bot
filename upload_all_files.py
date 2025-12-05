#!/usr/bin/env python3
"""
SFTP Upload Script for DetendezBot
Uploads all files in the current directory to a remote server via SFTP
"""

import os
import sys
import stat
import paramiko
from pathlib import Path
from typing import List, Set
import logging
from getpass import getpass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SFTPUploader:
    """Handles SFTP upload of all files to the remote server"""
    
    def __init__(self):
        # SFTP Configuration - Set these in your .env file or modify directly
        self.hostname = os.getenv('SFTP_HOST', 'your-server.com')
        self.port = int(os.getenv('SFTP_PORT', '22'))
        self.username = None  # Will be prompted
        self.password = None  # Will be prompted
        self.remote_path = '/home'  # Will be updated based on username
        
        # Local configuration
        self.local_path = Path.cwd()
        
        # Files and directories to exclude from upload
        self.exclude_patterns: Set[str] = {
            '.git',
            '.gitignore',
            '__pycache__',
            '*.pyc',
            '*.pyo',
            '.DS_Store',
            'Thumbs.db',
            '*.tmp',
            '*.swp',
            '.vscode',
            '.idea',
            'venv',
            'env',
            '.env',
            'node_modules',
            '*.log'
        }
        
        # SFTP connection
        self.ssh_client = None
        self.sftp_client = None
    
    def should_exclude(self, path: Path) -> bool:
        """Check if a file or directory should be excluded from upload"""
        path_str = str(path).replace('\\', '/')
        name = path.name
        
        # Check if this is the upload script itself
        if name == 'upload_all_files.py':
            return True
            
        for pattern in self.exclude_patterns:
            if pattern.startswith('*') and pattern.endswith('*'):
                # Contains pattern
                if pattern[1:-1] in name:
                    return True
            elif pattern.startswith('*'):
                # Ends with pattern
                if name.endswith(pattern[1:]):
                    return True
            elif pattern.endswith('*'):
                # Starts with pattern
                if name.startswith(pattern[:-1]):
                    return True
            else:
                # Exact match
                if name == pattern or path_str.endswith(f'/{pattern}'):
                    return True
        
        return False
    
    def get_credentials(self):
        """Get username and password from user"""
        print(f"Connecting to {self.hostname}:{self.port}")
        self.username = input("Username: ").strip()
        if not self.username:
            logger.error("Username is required")
            return False
        
        self.password = getpass("Password: ")
        if not self.password:
            logger.error("Password is required")
            return False
            
        # Update remote path to user's home directory
        self.remote_path = f'/home/{self.username}'
        return True
    
    def connect(self) -> bool:
        """Establish SFTP connection"""
        try:
            logger.info(f"Connecting to {self.hostname}:{self.port}")
            
            # Create SSH client
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect with password authentication
            self.ssh_client.connect(
                hostname=self.hostname,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=30
            )
            
            # Create SFTP client
            self.sftp_client = self.ssh_client.open_sftp()
            logger.info("SFTP connection established successfully")
            return True
            
        except paramiko.AuthenticationException:
            logger.error("Authentication failed - invalid username or password")
            return False
        except paramiko.SSHException as e:
            logger.error(f"SSH connection failed: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Failed to connect: {str(e)}")
            return False
    
    def disconnect(self):
        """Close SFTP connection"""
        if self.sftp_client:
            self.sftp_client.close()
        if self.ssh_client:
            self.ssh_client.close()
        logger.info("SFTP connection closed")
    
    def create_remote_directory(self, remote_dir: str):
        """Create directory on remote server if it doesn't exist"""
        try:
            self.sftp_client.stat(remote_dir)
        except FileNotFoundError:
            # Directory doesn't exist, create it
            parent_dir = os.path.dirname(remote_dir)
            if parent_dir and parent_dir != remote_dir:  # Avoid infinite recursion
                self.create_remote_directory(parent_dir)
            
            try:
                logger.info(f"Creating remote directory: {remote_dir}")
                self.sftp_client.mkdir(remote_dir)
            except Exception as e:
                logger.warning(f"Could not create directory {remote_dir}: {str(e)}")
    
    def upload_file(self, local_file: Path, remote_file: str) -> bool:
        """Upload a single file to the remote server"""
        try:
            # Create remote directory if needed
            remote_dir = os.path.dirname(remote_file)
            if remote_dir:
                self.create_remote_directory(remote_dir)
            
            # Upload file
            logger.info(f"Uploading: {local_file.name} -> {remote_file}")
            self.sftp_client.put(str(local_file), remote_file)
            
            # Set file permissions (make Python scripts executable)
            if local_file.suffix in ['.py', '.sh']:
                try:
                    self.sftp_client.chmod(remote_file, 0o755)
                except Exception as e:
                    logger.warning(f"Could not set permissions for {remote_file}: {str(e)}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to upload {local_file}: {str(e)}")
            return False
    
    def get_files_to_upload(self) -> List[Path]:
        """Get list of all files to upload"""
        files_to_upload = []
        
        for root, dirs, files in os.walk(self.local_path):
            root_path = Path(root)
            
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if not self.should_exclude(root_path / d)]
            
            for file in files:
                file_path = root_path / file
                if not self.should_exclude(file_path):
                    files_to_upload.append(file_path)
        
        return files_to_upload
    
    def preview_upload(self) -> List[Path]:
        """Preview what files would be uploaded"""
        files_to_upload = self.get_files_to_upload()
        
        print(f"\nFiles to be uploaded ({len(files_to_upload)} files):")
        print("-" * 60)
        
        for file_path in sorted(files_to_upload):
            relative_path = file_path.relative_to(self.local_path)
            file_size = file_path.stat().st_size
            size_str = f"{file_size:,} bytes" if file_size < 1024 else f"{file_size/1024:.1f} KB"
            print(f"  {relative_path} ({size_str})")
        
        print("-" * 60)
        total_size = sum(f.stat().st_size for f in files_to_upload)
        total_str = f"{total_size:,} bytes" if total_size < 1024*1024 else f"{total_size/(1024*1024):.1f} MB"
        print(f"Total: {len(files_to_upload)} files, {total_str}")
        
        return files_to_upload
    
    def upload_all(self) -> bool:
        """Upload all files to remote server"""
        # Get credentials
        if not self.get_credentials():
            return False
        
        # Preview files to upload
        files_to_upload = self.preview_upload()
        
        if not files_to_upload:
            logger.info("No files to upload")
            return True
        
        # Confirm upload
        print(f"\nDestination: {self.username}@{self.hostname}:{self.port}{self.remote_path}/")
        confirm = input("\nProceed with upload? (y/N): ").lower().strip()
        if confirm != 'y':
            logger.info("Upload cancelled by user")
            return False
        
        # Connect to server
        if not self.connect():
            return False
        
        try:
            # Upload files
            uploaded_count = 0
            failed_count = 0
            
            print(f"\nUploading {len(files_to_upload)} files...")
            print("=" * 60)
            
            for i, file_path in enumerate(files_to_upload, 1):
                # Calculate relative path
                relative_path = file_path.relative_to(self.local_path)
                remote_file_path = os.path.join(self.remote_path, str(relative_path)).replace('\\', '/')
                
                print(f"[{i:3d}/{len(files_to_upload)}] ", end="")
                
                if self.upload_file(file_path, remote_file_path):
                    uploaded_count += 1
                    print("✓")
                else:
                    failed_count += 1
                    print("✗")
            
            print("=" * 60)
            logger.info(f"Upload completed: {uploaded_count} uploaded, {failed_count} failed")
            
            if failed_count > 0:
                logger.warning(f"{failed_count} files failed to upload")
                return False
            else:
                logger.info("All files uploaded successfully!")
                return True
                
        except Exception as e:
            logger.error(f"Upload failed: {str(e)}")
            return False
        finally:
            self.disconnect()

def main():
    """Main function"""
    print("SFTP File Upload Script")
    print("=" * 40)
    print(f"Target Server: a remote server via SFTP")
    print(f"Local Directory: {Path.cwd()}")
    print()
    
    if len(sys.argv) > 1:
        if sys.argv[1] in ['--help', '-h']:
            print("Usage:")
            print("  python upload_all_files.py           Upload all files")
            print("  python upload_all_files.py --help    Show this help")
            print()
            print("This script will:")
            print("  1. Prompt for SSH credentials")
            print("  2. Show preview of files to upload")
            print("  3. Upload all files to /home/{username}/ on the server")
            print("  4. Maintain directory structure")
            print("  5. Skip common excluded files (.git, __pycache__, etc.)")
            return
    
    uploader = SFTPUploader()
    success = uploader.upload_all()
    
    if success:
        print("\n🎉 Upload completed successfully!")
    else:
        print("\n❌ Upload failed!")
        
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()