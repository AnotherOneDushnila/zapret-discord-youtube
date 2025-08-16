import os
import argparse
from typing import Callable, Tuple, List, Optional
from functools import wraps
import logging


class Service:

    def __init__(self, service_name: str) -> None:
        self.service_name = service_name.lower()

    def __str__(self):
        pass
        
    def argparse(self) -> argparse.ArgumentParser:
        if self.service_name == "ipset":
            parser = argparse.ArgumentParser(
            description="Domain to IP resolver and deduplicator"
            )

            parser.add_argument(
                "-f", 
                dest="filename",
                required=True,
                default="blocked-hosts.txt",
                help="File with domains to resolve (default: blocked-hosts.txt)"
            )

            parser.add_argument(
                "-m",
                dest="mode",
                choices=["1", "2"],
                required=True,
                help="Mode: 1 = deduplicate & sort, 2 = resolve & update ipset"
            )


            parser.add_argument(
                "-os", 
                dest="os_type",
                choices=["w", "l", "m"],
                help="OS type: w = Windows, l = Linux, m = macOS (required for mode 2)"
            )

            parser.add_argument(
                "-ip", 
                dest="ipv_mode",
                choices=["1", "2", "3"],
                type=str,
                help="IP version: 1 = IPv4, 2 = IPv6, 3 = both (required for mode 2)"
            )

            group = parser.add_mutually_exclusive_group()

            group.add_argument(
                "-c", 
                "--cidrs", 
                action="store_true", 
                help="Save as CIDR"
            )

            group.add_argument(
                "-i",
                "--ips", 
                action="store_true", 
                help="Save as IP"
            )

        elif self.service_name == "domains":
            parser = argparse.ArgumentParser(
            description="Domain to IP resolver and deduplicator"
            )

            parser.add_argument(
                "-f", 
                dest="filename",
                required=True,
                default="host.txt",
                help="File with hostname(s) to resolve (default: hosts.txt)"
            )

            parser.add_argument(
                "-b",
                dest="browser",
                choices=["chrome", "firefox", "edge"],
                default="chrome",
                required=True,
                help="Browser mode: chrome, firefox, edge (default: chrome)"
            )

        elif self.service_name == "dup-hosts":
            parser = argparse.ArgumentParser(
            description="Hostlist deduplicator"
            )

            parser.add_argument("-f", 
                dest="filename",
                required=True,
                default="hostlist.txt",
                help="File with domains to manage (default: blocked-hosts.txt)"
            )

        else:
            raise ValueError(f"Service '{self.service_name}' is not recognized.")
        
        return parser
    
   
    def find_file(self, filename: str, max_depth: int = 3) -> str:
        current_dir = os.path.abspath(os.curdir)
        for _ in range(max_depth):
            candidate = os.path.join(current_dir, filename)
            if os.path.isfile(candidate):
                return candidate
            current_dir = os.path.dirname(current_dir)
        raise FileNotFoundError(f"File '{filename}' not found within {max_depth} directory levels upward.")


    def log_file_change(self, func) -> Callable:
        @wraps(func)
        def wrapper(file_path: str, *args, **kwargs) -> None:
            before = []
            with open(file_path, "r", encoding="utf-8") as f:
                before = [line.strip() for line in f if line.strip()]

            func(file_path, *args, **kwargs)

            with open(file_path, "r", encoding="utf-8") as f:
                after = [line.strip() for line in f if line.strip()]

            added = len(after) - len(before)
            removed = len(before) - len(after)
            
            if added > 0:
                logging.info(f"{added} new entr{'y' if added == 1 else 'ies'} added.")
            if removed > 0:
                logging.info(f"{removed} duplicate entr{'y was' if removed == 1 else 'ies were'} removed.")
            if added == 0 and removed == 0:
                logging.info("No changes made to the file.")
            
        return wrapper
        
