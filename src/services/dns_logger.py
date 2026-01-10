'''
DNS logger module to log DNS queries to Supabase.
'''
import os
import sys
import hashlib

from src.exception.exception import CustomException
from src.logging.logging import logging

from datetime import datetime 
from dateutil import tz
from dotenv import load_dotenv

# Define Log path and Salt from environment variables
load_dotenv()
LOG_PATH = os.getenv("LOG_PATH")
SALT = os.getenv("SALT")

if not LOG_PATH or not SALT:
  logging.warning("LOG_PATH or SALT environment variables are not set.")
  raise ValueError("LOG_PATH and SALT must be set in environment variables.")

# Define month mapping
MONTHS = {
  "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
  "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
}

# Define local timezone
TIMEZONE = tz.tzlocal()

# Create a class to handle DNS logging
class DNSLogger:
  # Initialize with client IP
  def __init__(self):
    pass
  # Define method to hash client IP with salt
  def hash_client(self, client_ip: str) -> str:
    '''
    Hash the client IP with the provided salt using SHA-256.\n
    params:
    - client_ip: str : The client IP address to be hashed.\n
    returns:
    - str : The hashed client IP.
    '''
    try:
      # Define the salted IP
      logging.info(f"Hashing client IP: {client_ip} with salt.")
      salted_ip = SALT.encode("utf-8")
      hashed_ip = hashlib.sha256(salted_ip + client_ip.encode("utf-8")).hexdigest()
      
      logging.info("IP has been hashed successfully.")
      return hashed_ip[:24]
    except Exception as e:
      raise CustomException(e, sys)
  
  # Define method to parse a timestamp
  def parse_ts(self, mon: str, day: str, hhmmss: str) -> datetime:
    '''
    Parse timestamp from log entry components.\n
    params:
    - mon: str : Month abbreviation (e.g., 'Jan').\n
    - day: str : Day of the month.\n
    - hhmmss: str : Time in HH:MM:SS format.\n
    returns:
    - datetime : The parsed datetime object in local timezone.
    '''
    try:
      # Define current year
      now = datetime.now(TIMEZONE)
      year = now.year
      
      # Define local datetime
      logging.info(f"Parsing timestamp for {mon} {day} {hhmmss} {year}")
      dt_local = datetime(
        year, MONTHS[mon], int(day),
        int(hhmmss[0:2]), int(hhmmss[3:5]), int(hhmmss[6:8]),
        tzinfo=TIMEZONE
      )
      
      # Return the local datetime
      logging.info(f"Parsed local datetime: {dt_local}")
      return dt_local.astimezone(tz.tzutc())
    except Exception as e:
      raise CustomException(e, sys)