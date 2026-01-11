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
FORWARDED_RE = re.compile(
  r'^(?P<mon>\w{3})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+'
  r'dnsmasq\[(?P<pid>\d+)\]:\s+forwarded\s+(?P<domain>\S+)\s+to\s+(?P<upstream>\S+)'
)

REPLY_RE = re.compile(
  r'^(?P<mon>\w{3})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+'
  r'dnsmasq\[(?P<pid>\d+)\]:\s+reply\s+(?P<domain>\S+)\s+is\s+(?P<answer>.+)$'
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
  
  # Define pending dictionary for forwarded and reply events
  pending: dict = {}
  while True:
    
    # Read line from log file
    line = log_file.readline()
    line_s = line.strip()
    
    # Check if the line is not empty
    if not line:
      break
    
    # Make query match
    make_query = QUERY_RE.match(line_s)
    if make_query:
      parse_ts = dns.parse_ts(
        make_query.group("mon"),
        make_query.group("day"),
        make_query.group("time")
      )
      last_ts = parse_ts
      
      # Define DNS event
      client_ip = make_query.group("client_ip")
      client_id = dns.hash_client(client_ip)
      domain = make_query.group("domain").lower()
      pid = int(make_query.group("pid"))
      qtype = make_query.group("qtype")
      
      # Parse ts and define pending key
      ts_key = parse_ts.replace(microsecond=0).isoformat()
      pend_key = (pid, domain, ts_key)
      pend = pending.get(pend_key, {})
      
      # Encode raw line and hash it
      raw = line_s.encode("utf-8")
      hashed = hashlib.sha256(raw).hexdigest()
      
      # Append event to events list
      events.append({
      "ts": parse_ts.isoformat(),
      "source_host": SOURCE_HOST,
      "client_ip": client_ip,
      "client_id": client_id,
      "qtype": qtype,
      "domain": domain,
      "pid": pid,
      "raw_line": line_s,
      "event_hash": hashed,
      "upstream": pend.get("upstream"),
      "result": pend.get("result"),
      "answer": pend.get("answer"),
      })
      
      # Check if batch size is reached
      if len(events) >= BATCH_SIZE:
        supabase_handler.insert_events(events)
        events.clear()
      continue
      
    # Make forwarded match
    make_forward = FORWARDED_RE.match(line_s)
    if make_forward:
      parse_ts = dns.parse_ts(
        make_forward.group("mon"),
        make_forward.group("day"),
        make_forward.group("time")
      )
      # Define DNS forwarded event
      domain = make_forward.group("domain").lower()
      pid = int(make_forward.group("pid"))
      upstream = make_forward.group("upstream").split("#")[0]
      
      # Parse ts and define pending key
      ts_key = parse_ts.replace(microsecond=0).isoformat()
      pend_key = (pid, domain, ts_key)
      pending.setdefault(pend_key, {})["upstream"] = upstream
      continue
    
    # Make reply match
    reply_match = REPLY_RE.match(line_s)
    if reply_match:
      parse_ts = dns.parse_ts(
        reply_match.group("mon"),
        reply_match.group("day"),
        reply_match.group("time")
      )
      # Define DNS reply event
      domain = reply_match.group("domain").lower()
      pid = int(reply_match.group("pid"))
      answer = reply_match.group("answer").strip()
      
      # Check if answer indicates NXDOMAIN
      if "NXDOMAIN" in answer:
        result = "NXDOMAIN"
      elif "NODATA" in answer:
        result = "NODATA"
      elif "CNAME" in answer:
        result = "CNAME"
      else:
        result = "NOERROR"
      
      # Parse ts and define pending key
      ts_key = parse_ts.replace(microsecond=0).isoformat()
      pend_key = (pid, domain, ts_key)
      pending.setdefault(pend_key, {})["answer"] = answer
      pending.setdefault(pend_key, {})["result"] = result
      continue
    
  # Flush remaining events
  if events:
    supabase_handler.insert_events(events)
  
  # Record new offset
  new_offset = log_file.tell()
  supabase_handler.update_ingest_state(inode, new_offset, last_ts)

if SLEEP_SEC > 0:
  time.sleep(SLEEP_SEC)