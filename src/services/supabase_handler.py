'''
Supabase Handler Service to interact with Supabase database.
'''
import os
import sys

from supabase import create_client, Client
from datetime import datetime
from dateutil import tz
from typing import Dict

from src.exception.exception import CustomException
from src.logging.logging import logging

# Load supabase URL and Key from environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_API_KEY").strip()
SOURCE_HOST = os.environ.get("SOURCE_HOST").strip()
LOG_PATH = os.environ.get("LOG_PATH").strip()
if not SUPABASE_URL or not SUPABASE_KEY:
    logging.error("SUPABASE_URL or SUPABASE_API_KEY environment variables are not set.")
    raise ValueError("SUPABASE_URL and SUPABASE_API_KEY must be set in environment variables.")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
logging.info("Supabase client initialized successfully.")

# Define a class to handle Supabase operations
class SupabaseHandler:
  def __init__(self, inode: int, offset: int, last_ts: datetime | None, events, supabase: Client = supabase):
     self.inode = inode
     self.offset = offset
     self.last_ts = last_ts
     self.events = events
     self.supabase = supabase
    
  # Define method to ingest log metadata
  def get_ingest_state(self) -> Dict:
    try:
      # Define query to get ingest state
      logging.info("Fetching ingest state from Supabase.")
      response = self.supabase.table("ingest_state").select("*").eq("id", 1).execute()
      
      # Check if response has data
      if not response.data or len(response.data) == 0:
        logging.warning("No ingest state found with id 1.")
        return {}
      
      # Return the ingest state
      return {
        "inode": response.data[0]["inode"],
        "offset": response.data[0]["offset"],
        "last_ts": response.data[0]["last_ts"]
      }
    except Exception as e:
      raise CustomException(e, sys)
  
  # Define method to update log metadata
  def update_ingest_state(self) -> None:
    try:
      # Define payload
      payload = {
        "source_host": SOURCE_HOST,
        "log_path": LOG_PATH,
        "last_inode": self.inode,
        "last_offset": self.offset,
        "last_ts": self.last_ts.isoformat() if self.last_ts else None,
        "updated_at": datetime.now(tz.tzutc()).isoformat()
      }
      self.supabase.table("ingest_state").upsert(payload).execute()
    except Exception as e:
      raise CustomException(e, sys)
  
  # Define method to inser DNS events
  def insert_events(self) -> None:
    try:
      # Insert events
      logging.info(f"Inserting {len(self.events)} DNS events into Supabase.")
      self.supabase.table("dns_events").upsert(self.events, on_conflict="ts, client_ip, qtype, domain, pid").execute()
      logging.info("DNS events inserted successfully.")
    except Exception as e:
      raise CustomException(e, sys)