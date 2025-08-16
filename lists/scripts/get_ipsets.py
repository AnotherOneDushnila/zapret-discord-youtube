import os
import subprocess, logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio, aiohttp
import json
import ipaddress
from typing import Tuple, List, Optional, Set, Union
from service import Service


CIDR_CACHE_FILE = "cidr_cache.json"
service = Service("ipset")
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')



def nslookup(cmd: List[str]) -> str:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        return res.stdout if res.returncode == 0 else ""
    except Exception as e:
        logging.warning(f"Failed to run {cmd}: {e}")
        return ""


def resolve_domains(domain_file: str, os_type: str, ipv_mode: str) -> Tuple[Optional[str], Optional[str]]:
    try:
        domain_list_path = service.find_file(domain_file)
    except FileNotFoundError as e:
        logging.error("File not found!", exc_info=True)
        return None, None

    try:
        with open(domain_list_path, "r", encoding="utf-8") as file:
            domains = [line for line in file if line.strip()]
            cmds = []

            for domain in domains:
                if os_type == "w":
                    if ipv_mode in ("1", "3"):
                        cmds.append(["powershell", "-Command", f"nslookup -type=A {domain}"])
                    if ipv_mode in ("2", "3"):
                        cmds.append(["powershell", "-Command", f"nslookup -type=AAAA {domain}"])
                elif os_type in ("m", "l"):
                    if ipv_mode in ("1", "3"):
                        cmds.append(["nslookup", "-type=A", domain])
                    if ipv_mode in ("2", "3"):
                        cmds.append(["nslookup", "-type=AAAA", domain])
                else:
                    logging.error("Invalid OS type. Use 'w' (Windows), 'l' (Linux) or 'm' (macOS).")
                    return None, None

            output = ""
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(nslookup, cmd) for cmd in cmds]
                for future in as_completed(futures):
                    output += future.result()

            return output, domain_list_path

    except Exception as e:
        logging.error("Unexpected error occurred during domain resolution.", exc_info=True)
        return None, None


def load_cache_from_disk() -> dict[str, List[str]]:
    if os.path.exists(CIDR_CACHE_FILE):
        with open(CIDR_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache_to_disk(cache: dict[str, List[str]]):
    with open(CIDR_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


async def get_cidrs(ips: List[str]) -> Set[str]:
    results = []
    cache = load_cache_from_disk()

    async def fetch(ip: str, session: aiohttp.ClientSession) -> List[str]:
        key = f"cidr:{ip}"
        
        if ip in cache:
            logging.debug(f"[REDIS CACHE] CIDRs for {ip} found and executed.")
            return json.loads(cache[key])
        
        url = f"https://rdap.db.ripe.net/ip/{ip}"
        try:
            async with session.get(url, timeout=10) as response:
                if response.status != 200:
                    logging.warning(f"Failed to fetch CIDR for {ip}: HTTP {response.status}")
                    return []

                data = await response.json()
                cidr_entries = data.get("cidr0_cidrs", [])
                cidrs = [f"{entry['v4prefix']}/{entry['length']}" for entry in cidr_entries if 'v4prefix' in entry] + \
                         [f"{entry['v6prefix']}/{entry['length']}" for entry in cidr_entries if 'v6prefix' in entry]
                
                cache[key] = cidrs
                return cidrs
            
        except Exception:
            return []

    async with aiohttp.ClientSession() as session:
        tasks = [fetch(ip, session) for ip in ips]
        cidr_lists = await asyncio.gather(*tasks)
        for cidrs in cidr_lists:
            for cidr in cidrs:
                results.append(cidr)

    save_cache_to_disk(cache)
    
    return set(results)


@service.log_file_change
def remove_duplicates(filepath: str) -> None:
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    unique = set(line.strip() for line in lines if line.strip())
    sorted_unique = sort_ips(unique)

    with open(filepath, "w", encoding="utf-8") as f:
        for line in sorted_unique:
            f.write(line + "\n")


def sort_ips(array: set[str]) -> List[str]:
    def parse(cidr: str) -> Tuple[int, int, int]:
        net = ipaddress.ip_network(cidr, strict=False)

        ipv6 = 1 if net.version == 6 else 0

        return (ipv6, int(net.network_address), net.prefixlen)
    
    return sorted(array, key=parse)


def separate_ips(log: str, ipv_mode: str) -> Optional[Union[List[str], List[str]]]:
    excluded_ips = {'1.1.1.1', '8.8.8.8', '8.8.4.4', '192.168.0.1'}
    ipv6_list, ipv4_list = [], []

    lines = log.splitlines()
    total_lines = len(lines)
    i = 0

    while i < total_lines:
        line = lines[i].strip()

        ip_candidates = []

        if line.startswith("Address:") or line.startswith("Addresses:"):
            address_part = line.partition(":")[2].strip()
            if address_part:
                ip_candidates.append(address_part)
            else:
                i += 1
                while i < total_lines:
                    next_line = lines[i].strip()
                    if not next_line or next_line.startswith(("Server:", "Name:", "Address", "Alias")):
                        break
                    ip_candidates.extend(next_line.split())
                    i += 1
                i -= 1

        else:
            parts = line.split()
            if len(parts) == 1:
                ip_candidates.append(parts[0])
           

            for ip in ip_candidates:
                try:
                    ip = ip.strip()
                    ip_obj = ipaddress.ip_address(ip)
                    if ip in excluded_ips or ip_obj.is_link_local:
                        logging.debug(f"Skipping excluded or link-local IP: {ip}")
                        continue
                    if ip_obj.version == 4 and ipv_mode in ('1', '3'):
                        ipv4_list.append(ip)
                    elif ip_obj.version == 6 and ipv_mode in ('2', '3'):
                        if ip_obj.compressed == "::":
                            logging.debug("Skipping compressed IPv6 address (::)")
                            continue
                        ipv6_list.append(ip)
                except ValueError:
                    continue

        i += 1

    if not ipv4_list and not ipv6_list:
        logging.warning("No valid IPs found in nslookup output.")
        return
    return ipv4_list, ipv6_list


def process_ips(log: str, domain_list_path: str, ipv_mode: str) -> None:
    ipv4_list, ipv6_list = separate_ips(log, ipv_mode)
    ipv4_list, ipv6_list = list(set(ipv4_list)), list(set(ipv6_list))
    total_ips = len(ipv4_list) + len(ipv6_list)

    if ipv_mode == '1':
        if ipv4_list:
            ipv4_output_file = os.path.join(
                os.path.dirname(domain_list_path), 
                f"ips-ipv4-{os.path.basename(domain_list_path)}"
            )

            with open(ipv4_output_file, "a", encoding="utf-8") as f:
                for ip in ipv4_list:
                    f.write(ip + "\n")

            logging.info('IPv4 info:')
            remove_duplicates(ipv4_output_file)


        else:
            logging.info("No IPv4 addersses found.")


    elif ipv_mode == '2':
        if ipv6_list:
            ipv6_output_file = os.path.join(
                os.path.dirname(domain_list_path),
                f"ips-ipv6-{os.path.basename(domain_list_path)}"
            )

            with open(ipv6_output_file, "a", encoding="utf-8") as f:
                for ip in ipv6_list:
                    f.write(ip + "\n")

            logging.info('IPv6 info:')
            remove_duplicates(ipv6_output_file)

        else:
            logging.info("No IPv6 addresses found.")
        

    elif ipv_mode == '3':
        if ipv4_list:
            ipv4_output_file = os.path.join(
                os.path.dirname(domain_list_path), 
                f"ips-ipv4-{os.path.basename(domain_list_path)}"
            )

            with open(ipv4_output_file, "a", encoding="utf-8") as f:
                for ip in ipv4_list:
                    f.write(ip + "\n")

            logging.info('IPv4 info:')
            remove_duplicates(ipv4_output_file)

        else:
            logging.info("No IPv4 adddresses created.")


        if ipv6_list:
            ipv6_output_file = os.path.join(
                os.path.dirname(domain_list_path),
                f"ips-ipv6-{os.path.basename(domain_list_path)}"
            )

            with open(ipv6_output_file, "a", encoding="utf-8") as f:
                for ip in ipv6_list:
                    f.write(ip + "\n")

            logging.info('IPv6 info:')
            remove_duplicates(ipv6_output_file)
            
        else:
            logging.info("No IPv6 addresses created.")
        
        logging.info(f"Extracted {total_ips} IPs.")

    else:
        logging.error("Invalid IP version mode!")
        raise ValueError("Invalid IP version mode! Choose from (1, 2, 3).")


def process_cidrs(log, domain_list_path: str, ipv_mode: str) -> None:
    ipv4_list, ipv6_list = separate_ips(log, ipv_mode)
    ipv4_list, ipv6_list = list(set(ipv4_list)), list(set(ipv6_list))
    total_cidrs = 0

    if ipv_mode == '1':
        ipv4_cidrs = asyncio.run(get_cidrs(ipv4_list))
        if ipv4_cidrs:
            ipv4_output_file = os.path.join(
                os.path.dirname(domain_list_path), 
                f"ipset-ipv4-{os.path.basename(domain_list_path)}"
            )

            with open(ipv4_output_file, "a", encoding="utf-8") as f:
                for cidr in ipv4_cidrs:
                    f.write(str(cidr) + "\n")

            logging.info('IPv4 info:')
            remove_duplicates(ipv4_output_file)

            total_cidrs += len(ipv4_cidrs)

        else:
            logging.info("No IPv4 cidrs found.")


    elif ipv_mode == '2':
        ipv6_cidrs = asyncio.run(get_cidrs(ipv6_list))
        if ipv6_cidrs:
            ipv6_output_file = os.path.join(
                os.path.dirname(domain_list_path),
                f"ipset-ipv6-{os.path.basename(domain_list_path)}"
            )

            with open(ipv6_output_file, "a", encoding="utf-8") as f:
                for cidr in ipv6_cidrs:
                    f.write(str(cidr) + "\n")

            logging.info('IPv6 info:')
            remove_duplicates(ipv6_output_file)

            total_cidrs += len(ipv6_cidrs)

        else:
            logging.info("No IPv6 cidrs found.")
        

    elif ipv_mode == '3':
        ipv4_cidrs, ipv6_cidrs = asyncio.run(get_cidrs(ipv4_list)), asyncio.run(get_cidrs(ipv6_list))

        if ipv4_cidrs:
            ipv4_output_file = os.path.join(
                os.path.dirname(domain_list_path), 
                f"ipset-ipv4-{os.path.basename(domain_list_path)}"
            )

            with open(ipv4_output_file, "a", encoding="utf-8") as f:
                for cidr in ipv4_cidrs:
                    f.write(str(cidr) + "\n")

            logging.info('IPv4 info:')
            remove_duplicates(ipv4_output_file)

            total_cidrs += len(set(ipv4_cidrs))

        else:
            logging.info("No IPv4 cidrs created.")

        if ipv6_cidrs:
            ipv6_output_file = os.path.join(
                os.path.dirname(domain_list_path),
                f"ipset-ipv6-{os.path.basename(domain_list_path)}"
            )

            with open(ipv6_output_file, "a", encoding="utf-8") as f:
                for cidr in ipv6_cidrs:
                    f.write(str(cidr) + "\n")

            logging.info('IPv6 info:')
            remove_duplicates(ipv6_output_file)

            total_cidrs += len(ipv6_cidrs)
            
        else:
            logging.info("No IPv6 cidrs created.")

    else:
        logging.error("Invalid IP version mode!")
        raise ValueError("Invalid IP version mode! Choose from (1, 2, 3).")


def format_output(log: str, domain_list_path: str, ipv_mode: str, flag: str = ["cidrs", "ips"]) -> None:
    if flag == "cidrs":
        process_cidrs(log, domain_list_path, ipv_mode)

    elif flag == "ips":
        process_ips(log, domain_list_path, ipv_mode)
        
    else:
        logging.error("Invalid script mode!")
        raise ValueError("Invalid script mode! Choose from ('cidrs', 'scripts' | '-c', '-i').")
        


def main() -> None:
    args = service.argparse().parse_args()

    if args.mode == "1":
        try:
            filepath = service.find_file(args.filename)
            remove_duplicates(filepath)
        except FileNotFoundError:
            logging.error(f"File '{args.filename}' not found.")

    elif args.mode == "2":
        log_data, domain_path = resolve_domains(args.filename, args.os_type, args.ipv_mode)

        if log_data and domain_path:
            flag = "cidrs" if args.cidrs else "ips"
            format_output(log_data, domain_path, args.ipv_mode, flag)
        else:
            logging.error("Failed to get IPs. Exiting.")
    else:
        logging.error("Invalid mode. Choose 1 or 2.")



if __name__ == "__main__":
    main()
