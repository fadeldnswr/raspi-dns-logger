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
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_API_KEY")
SOURCE_HOST = os.environ.get("SOURCE_HOST")
LOG_PATH = os.environ.get("LOG_PATH")
if not SUPABASE_URL or not SUPABASE_KEY:
    logging.error("SUPABASE_URL or SUPABASE_API_KEY environment variables are not set.")
    raise ValueError("SUPABASE_URL and SUPABASE_API_KEY must be set in environment variables.")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
logging.info("Supabase client initialized successfully.")

# Define a class to handle Supabase operations
class SupabaseHandler:
  def __init__(self, supabase: Client = supabase):
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
      
      # Retrieve and log the ingest state
      row = response.data[0]
      
      # Return the ingest state
      return {
        "inode": row.get("last_inode"),
        "last_offset": row.get("last_offset", 0),  
        "last_ts": row.get("last_ts")
      }
    except Exception as e:
      raise CustomException(e, sys)
  
  # Define method to update log metadata
  def update_ingest_state(self, inode: int, offset: int, last_ts: datetime | None, ) -> None:
    try:
      # Define payload
      payload = {
        "id": 1,
        "source_host": SOURCE_HOST,
        "log_path": LOG_PATH,
        "last_inode": inode,
        "last_offset": offset,
        "last_ts": last_ts.isoformat() if last_ts else None,
        "updated_at": datetime.now(tz.tzutc()).isoformat()
      }
      self.supabase.table("ingest_state").upsert(payload).execute()
    except Exception as e:
      raise CustomException(e, sys)
  
  # Define method to inser DNS events
  def insert_events(self, events) -> None:
    try:
      # Insert events
      logging.info(f"Inserting {len(events)} DNS events into Supabase.")
      self.supabase.table("dns_events").upsert(events, on_conflict="ts,client_ip,qtype,domain,pid").execute()
      logging.info("DNS events inserted successfully.")
    except Exception as e:
      raise CustomException(e, sys)