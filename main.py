'''
Main module for Raspi DNS Logger application.
'''
import os
import re
import sys
import time
import hashlib

from src.services.dns_logger import DNSLogger
from src.services.supabase_handler import SupabaseHandler
from src.logging.logging import logging
from src.exception.exception import CustomException
from dotenv import load_dotenv

# Define constants from environment variables
load_dotenv()
LOG_PATH = os.getenv("LOG_PATH")
SOURCE_HOST = os.getenv("SOURCE_HOST")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000"))
SLEEP_SEC = int(os.getenv("SLEEP_SEC", "0"))

# Define Query for regex pattern matching
QUERY_RE = re.compile(
  r'^(?P<mon>\w{3})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+'
  r'dnsmasq\[(?P<pid>\d+)\]:\s+query\[(?P<qtype>[A-Z0-9]+)\]\s+'
  r'(?P<domain>\S+)\s+from\s+(?P<client_ip>\d{1,3}(?:\.\d{1,3}){3})'
)

# Define the file status from LOG PATH
try:
  file_status = os.stat(LOG_PATH)
except Exception as e:
  logging.error(f"Failed to get file status for {LOG_PATH}: {e}")
  raise CustomException(e, sys)

# Define supabase handler and dns logger instances
supabase_handler = SupabaseHandler()
dns = DNSLogger()

# Fetch current ingest state
dns_state = supabase_handler.get_ingest_state() 

# Define inode and offset
inode = file_status.st_ino
last_inode = dns_state.get("last_inode", None)
last_offset = int(dns_state.get("last_offset", 0) or 0)

# Create instance of SupabaseHandler and DNSLogger

# Check if inode changed, then start from zero
if last_inode and int(last_inode) != inode:
  logging.info("Log file inode has changed. Resetting offset to 0.")
  last_offset = 0

# Create list of events to batch insert
events: list = []
last_ts = None

# Open file and read from last offset
with open(LOG_PATH, "r", encoding="utf-8", errors="ignore") as log_file:
  # Seek to last offset
  log_file.seek(last_offset)
  while True:
    
    # Read line from log file
    line = log_file.readline()
    
    # Check if the line is not empty
    if not line:
      break
    
    # Match the line with regex
    match = QUERY_RE.match(line)
    if not match:
      continue
    
    # Parse timestamp
    parse_ts = dns.parse_ts(match.group("mon"), match.group("day"), match.group("time"))
    last_ts = parse_ts
    
    # Hash client IP
    hashed_ip = dns.hash_client(match.group("client_ip"))
    
    # Create hash lib for hash event
    raw = line.strip().encode("utf-8")
    hashed_event = hashlib.sha256(raw).hexdigest()

    # Create event dictionary
    events.append({
      "ts": parse_ts.isoformat(),
      "source_host": SOURCE_HOST,
      "client_ip": match.group("client_ip"),
      "client_id": hashed_ip,
      "qtype": match.group("qtype"),
      "domain": match.group("domain").lower(),
      "pid": int(match.group("pid")),
      "raw_line": line.strip(),
      "event_hash": hashed_event
    })
    
    # Check if batch size is reached
    if len(events) >= BATCH_SIZE:
      supabase_handler.insert_events(events)
      events.clear()
  
  # Flush remaining events
  if events:
    supabase_handler.insert_events(events)
  
  # Record new offset
  new_offset = log_file.tell()
  supabase_handler.update_ingest_state(inode, new_offset, last_ts)

if SLEEP_SEC > 0:
  time.sleep(SLEEP_SEC)