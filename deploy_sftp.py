#!/usr/bin/env python3
"""
SFTP Deployment Script for DetendezBot
Uploads all files in the current directory to a remote server via SFTP
while maintaining the directory structure.
"""

import os
import sys
import stat
import paramiko
from pathlib import Path
from typing import List, Set
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SFTPDeployer:
    """Handles SFTP deployment of files to remote server"""
    
    def __init__(self):
        # SFTP Configuration - Set these in your .env file or modify directly
        self.hostname = os.getenv('SFTP_HOST', 'your-server.com')
        self.port = int(os.getenv('SFTP_PORT', '22'))
        self.username = os.getenv('SFTP_USER', 'your-username')
        self.password = os.getenv('SFTP_PASSWORD', '')  # Leave empty to use key auth
        self.private_key_path = os.getenv('SFTP_KEY_PATH', '~/.ssh/id_rsa')
        self.remote_path = os.getenv('SFTP_REMOTE_PATH', '/path/to/your/bot')
        
        # Local configuration
        self.local_path = Path.cwd()
        
        # Files and directories to exclude from upload
        self.exclude_patterns: Set[str] = {
            '.git',
            '__pycache__',
            '.gitignore',
            '*.pyc',
            '*.pyo',
            '*.log',
            'bot_data.db',  # Don't overwrite production database
            'youtube_cookies.txt',  # Keep production cookies
            '.env',  # Don't overwrite production environment
            'deploy_sftp.py',  # Don't upload this script itself
            '.DS_Store',
            'Thumbs.db',
            '*.tmp',
            '*.swp',
            '.vscode',
            '.idea'
        }
        
        # SFTP connection
        self.ssh_client = None
        self.sftp_client = None
    
    def should_exclude(self, path: Path) -> bool:
        """Check if a file or directory should be excluded from upload"""
        path_str = str(path)
        name = path.name
        
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
                if name == pattern or path_str.endswith(f'/{pattern}') or path_str.endswith(f'\\{pattern}'):
                    return True
        
        return False
    
    def connect(self) -> bool:
        """Establish SFTP connection"""
        try:
            logger.info(f"Connecting to {self.hostname}:{self.port}")
            
            # Create SSH client
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect with password or key authentication
            if self.password:
                logger.info("Using password authentication")
                self.ssh_client.connect(
                    hostname=self.hostname,
                    port=self.port,
                    username=self.username,
                    password=self.password
                )
            else:
                logger.info("Using key authentication")
                private_key_path = os.path.expanduser(self.private_key_path)
                if os.path.exists(private_key_path):
                    try:
                        private_key = paramiko.RSAKey.from_private_key_file(private_key_path)
                    except paramiko.ssh_exception.PasswordRequiredException:
                        key_password = input("Enter private key password: ")
                        private_key = paramiko.RSAKey.from_private_key_file(private_key_path, password=key_password)
                    
                    self.ssh_client.connect(
                        hostname=self.hostname,
                        port=self.port,
                        username=self.username,
                        pkey=private_key
                    )
                else:
                    logger.error(f"Private key file not found: {private_key_path}")
                    return False
            
            # Create SFTP client
            self.sftp_client = self.ssh_client.open_sftp()
            logger.info("SFTP connection established successfully")
            return True
            
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
            if parent_dir != remote_dir:  # Avoid infinite recursion
                self.create_remote_directory(parent_dir)
            
            logger.info(f"Creating remote directory: {remote_dir}")
            self.sftp_client.mkdir(remote_dir)
    
    def upload_file(self, local_file: Path, remote_file: str) -> bool:
        """Upload a single file to the remote server"""
        try:
            # Create remote directory if needed
            remote_dir = os.path.dirname(remote_file)
            if remote_dir:
                self.create_remote_directory(remote_dir)
            
            # Upload file
            logger.info(f"Uploading: {local_file} -> {remote_file}")
            self.sftp_client.put(str(local_file), remote_file)
            
            # Set file permissions (make scripts executable)
            if local_file.suffix in ['.py', '.sh']:
                try:
                    self.sftp_client.chmod(remote_file, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | 
                                          stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
                except:
                    pass  # Ignore chmod errors
            
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
    
    def deploy(self) -> bool:
        """Deploy all files to remote server"""
        if not self.connect():
            return False
        
        try:
            # Get list of files to upload
            files_to_upload = self.get_files_to_upload()
            logger.info(f"Found {len(files_to_upload)} files to upload")
            
            # Confirm deployment
            print(f"\nDeployment Configuration:")
            print(f"Local Path: {self.local_path}")
            print(f"Remote Host: {self.hostname}:{self.port}")
            print(f"Remote Path: {self.remote_path}")
            print(f"Files to upload: {len(files_to_upload)}")
            
            if input("\nProceed with deployment? (y/N): ").lower() != 'y':
                logger.info("Deployment cancelled by user")
                return False
            
            # Upload files
            uploaded_count = 0
            failed_count = 0
            
            for file_path in files_to_upload:
                # Calculate relative path
                relative_path = file_path.relative_to(self.local_path)
                remote_file_path = os.path.join(self.remote_path, str(relative_path)).replace('\\', '/')
                
                if self.upload_file(file_path, remote_file_path):
                    uploaded_count += 1
                else:
                    failed_count += 1
            
            logger.info(f"Deployment completed: {uploaded_count} uploaded, {failed_count} failed")
            return failed_count == 0
            
        except Exception as e:
            logger.error(f"Deployment failed: {str(e)}")
            return False
        finally:
            self.disconnect()
    
    def show_config(self):
        """Display current configuration"""
        print("SFTP Deployment Configuration:")
        print(f"Host: {self.hostname}")
        print(f"Port: {self.port}")
        print(f"Username: {self.username}")
        print(f"Authentication: {'Password' if self.password else 'Private Key'}")
        print(f"Private Key Path: {self.private_key_path}")
        print(f"Remote Path: {self.remote_path}")
        print(f"Local Path: {self.local_path}")
        print(f"Excluded patterns: {', '.join(sorted(self.exclude_patterns))}")

def main():
    """Main function"""
    deployer = SFTPDeployer()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--config':
            deployer.show_config()
            return
        elif sys.argv[1] == '--help':
            print("SFTP Deployment Script")
            print("Usage:")
            print("  python deploy_sftp.py           Deploy files")
            print("  python deploy_sftp.py --config  Show configuration")
            print("  python deploy_sftp.py --help    Show this help")
            print("\nEnvironment Variables:")
            print("  SFTP_HOST         - Remote server hostname")
            print("  SFTP_PORT         - SSH port (default: 22)")
            print("  SFTP_USER         - SSH username")
            print("  SFTP_PASSWORD     - SSH password (optional, uses key auth if empty)")
            print("  SFTP_KEY_PATH     - Path to private key (default: ~/.ssh/id_rsa)")
            print("  SFTP_REMOTE_PATH  - Remote directory path")
            return
    
    # Validate configuration
    if not all([deployer.hostname, deployer.username, deployer.remote_path]):
        logger.error("Missing required configuration. Please set SFTP_HOST, SFTP_USER, and SFTP_REMOTE_PATH")
        logger.info("Run 'python deploy_sftp.py --help' for configuration details")
        sys.exit(1)
    
    # Deploy
    success = deployer.deploy()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 