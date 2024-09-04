#!/usr/bin/python3
import logging
import json
from moralis import evm_api
moralis_api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJub25jZSI6IjAyNDU2YzIzLWY0MTEtNDQ1NC05ODQyLWM2MjM5ZDM0NjU4MiIsIm9yZ0lkIjoiNDA0NDYxIiwidXNlcklkIjoiNDE1NTk4IiwidHlwZUlkIjoiY2NkOTgzNWUtM2Q5Ny00NWM0LWE4YWUtZjUyNjY0M2I0NWQ2IiwidHlwZSI6IlBST0pFQ1QiLCJpYXQiOjE3MjM1MDI4ODQsImV4cCI6NDg3OTI2Mjg4NH0.tdBEUcaxi-op9ysnyLHpOm8mo8zyl5phdlBuh1TXTrM"
bnb_address = "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c"
logging.basicConfig(level=logging.CRITICAL)
logger = logging.getLogger()

class ArbitrageDetector:
    def __init__(self):
        self.balances: Dict[str, Dict[str, int]] = {}

