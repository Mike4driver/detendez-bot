#!/usr/bin/env python3
import re
import sys
import os

filename = 'upload_all_files.py'
if not os.path.exists(filename):
    sys.exit(0)

with open(filename, 'r') as f:
    content = f.read()

original = content

# Replacements
content = re.sub(r'bot-service-na-west-05\.cybrancee\.com:2022', 'a remote server via SFTP', content)
content = re.sub(r'# SFTP Configuration for bot-service-na-west-05\.cybrancee\.com', 
                 '# SFTP Configuration - Set these in your .env file or modify directly', content)
content = re.sub(r"self\.hostname = 'bot-service-na-west-05\.cybrancee\.com'", 
                 "self.hostname = os.getenv('SFTP_HOST', 'your-server.com')", content)
content = re.sub(r'self\.port = 2022', 
                 "self.port = int(os.getenv('SFTP_PORT', '22'))", content)

if content != original:
    with open(filename, 'w') as f:
        f.write(content)
    # Also add dotenv if needed
    if 'from dotenv import load_dotenv' not in content and 'import json' in content:
        with open(filename, 'r') as f:
            lines = f.readlines()
        with open(filename, 'w') as f:
            for i, line in enumerate(lines):
                f.write(line)
                if line.strip() == 'import json' and i + 1 < len(lines) and 'from dotenv' not in lines[i+1]:
                    f.write('from dotenv import load_dotenv\n\n# Load environment variables\nload_dotenv()\n')
