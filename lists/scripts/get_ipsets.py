import os
import subprocess, logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio, aiohttp
import json
import ipaddress, psutil, socket
from typing import Tuple, List, Optional, Set, Union
from service import Service




CIDR_CACHE_FILE = "cidr_cache.json"
service = Service("ipset")
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')



def run_proc(cmd: List[str]) -> str:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        return res.stdout if res.returncode == 0 else ""
    except Exception as e:
        logging.warning(f"Failed to run {cmd}: {e}")
        return ""


def resolve_domains(domain_file: str, os_type: str, ipv_mode: str, testmode: str) -> Tuple[Optional[str], Optional[str]]:
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
                if testmode == 'nslookup':
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
                

                elif testmode == "dig":
                    if os_type in ("m", "l"):
                        if ipv_mode in ("1", "3"):
                            cmds.append(["dig", "+short", domain, "A"])
                        if ipv_mode in ("2", "3"):
                            cmds.append(["dig", "+short", domain, "AAAA"])

                    elif os_type == "w":
                        if ipv_mode in ("1", "3"):
                            cmds.append(["dig", "+short", domain, "A"])
                        if ipv_mode in ("2", "3"):
                            cmds.append(["dig", "+short", domain, "AAAA"])

                    else:
                        logging.error("Invalid OS type. Use 'w' (Windows), 'l' (Linux) or 'm' (macOS).")
                        return None, None

                elif testmode == "curl":
                    if os_type in ("m", "l"):
                        if ipv_mode in ("1", "3"):
                            cmds.append(["dig", "+short", domain, "A"])
                        if ipv_mode in ("2", "3"):
                            cmds.append(["dig", "+short", domain, "AAAA"])

                    elif os_type == "w":
                        if ipv_mode in ("1", "3"):
                            cmds.append(["dig", "+short", domain, "A"])
                        if ipv_mode in ("2", "3"):
                            cmds.append(["dig", "+short", domain, "AAAA"])

                    else:
                        logging.error("Invalid OS type. Use 'w' (Windows), 'l' (Linux) or 'm' (macOS).")
                        return None, None


            output = ""
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(run_proc, cmd) for cmd in cmds]
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
    flag = "a" if os.path.exists(f"./{CIDR_CACHE_FILE}") else "w"
    with open(CIDR_CACHE_FILE, mode = flag, encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


async def get_cidrs(ips: List[str], cache_flag: bool) -> Set[str]:
    results = []

    if cache_flag:
        cache = load_cache_from_disk()   
    else:
        cache = None

    async def fetch(ip: str, session: aiohttp.ClientSession) -> List[str]:
        key = f"cidr:{ip}"
        
        if cache and key in cache:
            logging.debug(f"[CACHE] CIDRs for {ip} found and executed.")
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
                
                if cache_flag:
                    if key not in cache:
                        cache[key] = cidrs

                return cidrs
            
        except Exception as e:
            logging.error(f"Error fetching CIDR for {ip}: {e}", exc_info=True)
            return []

    async with aiohttp.ClientSession() as session:
        tasks = [fetch(ip, session) for ip in ips]
        cidr_lists = await asyncio.gather(*tasks)
        for cidrs in cidr_lists:
            for cidr in cidrs:
                results.append(cidr)

    if cache_flag:
        save_cache_to_disk(cache)
    
    return set(results)


def get_port(port: int) -> Optional[List[str]]:
    result = set()
    try:
        for conn in psutil.net_connections(kind='inet'):
            if conn.raddr and conn.status == psutil.CONN_ESTABLISHED:
                if conn.raddr[1] == port:
                    result.add(conn.raddr[0])
    except Exception as e:
        logging.error(f"Error getting port connections: {e}", exc_info=True)
        return None
    return list(result)


def ip2host(ips: List[str], port: int, filename: str = "port_connections.txt") -> Optional[str]:
    seen = set()
    output_lines = []

    for ip in ips:
        try:
            domain = socket.gethostbyaddr(ip)[0]
            logging.info(f"{ip} resolved to {domain}")
        except Exception:
            domain = None
            logging.debug(f"Could not resolve {ip}")

        line = f"{domain} : {ip} : {port}" if domain else f"{ip} : {port}"
        if line not in seen:
            seen.add(line)
            output_lines.append(line)

    if output_lines:
        with open(filename, "a", encoding="utf-8") as f:
            for line in output_lines:
                f.write(line + "\n")

        logging.info(f"Saved {len(output_lines)} connection(s) to {filename}")
    else:
        logging.info("No new connections to save.")


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


def separate_ips(log: str, ipv_mode: str, testmode: str = ["nslookup", "dig"]) -> Optional[Union[List[str], List[str]]]:
    excluded_ips = {'1.1.1.1', '8.8.8.8', '8.8.4.4', '192.168.0.1'}
    ipv6_list, ipv4_list = [], []

    if testmode == "nslookup":
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


    elif testmode == "dig":
        for line in log.splitlines():
            line = line.strip()
            try:
                ip_obj = ipaddress.ip_address(line)
                if line in excluded_ips or ip_obj.is_link_local:
                    continue
                if ip_obj.version == 4 and ipv_mode in ('1', '3'):
                    ipv4_list.append(line)
                elif ip_obj.version == 6 and ipv_mode in ('2', '3'):
                    ipv6_list.append(line)
            except ValueError:
                continue
        

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


def process_cidrs(log, domain_list_path: str, ipv_mode: str, cache: bool) -> None:
    ipv4_list, ipv6_list = separate_ips(log, ipv_mode)
    ipv4_list, ipv6_list = list(set(ipv4_list)), list(set(ipv6_list))
    total_cidrs = 0

    if ipv_mode == '1':
        ipv4_cidrs = asyncio.run(get_cidrs(ipv4_list, cache))
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
        ipv6_cidrs = asyncio.run(get_cidrs(ipv6_list, cache))
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
        ipv4_cidrs, ipv6_cidrs = asyncio.run(get_cidrs(ipv4_list, cache)), asyncio.run(get_cidrs(ipv6_list, cache))

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
    
    
def format_output(log: str, domain_list_path: str, ipv_mode: str, cache: bool = False, flag: str = ["cidrs", "ips"], type: str = "nslookup") -> None:
    if flag == "cidrs":
        process_cidrs(log, domain_list_path, ipv_mode, cache)

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
        if args.os_type and args.ipv_mode and args.filename and args.testmode:
            log_data, domain_path = resolve_domains(args.filename, args.os_type, args.ipv_mode, args.testmode)

        if log_data and domain_path:
            flag = "cidrs" if args.cidrs else "ips"
            cache = True if args.cache else False
            format_output(log_data, domain_path, args.ipv_mode, cache, flag)
        else:
            logging.error("Failed to get IPs. Exiting.")
            
    elif args.mode == "3":
        if args.port_number:
            ips = get_port(args.port_number)
            if not ips:
                logging.warning(f"No active connections found on port {args.port_number}.")
            else:
                logging.info(f"Found {len(ips)} IP(s) on port {args.port_number}.")
                if args.filename:
                    ip2host(ips, args.port_number, args.filename)
                else:
                    ip2host(ips, args.port_number)
                
    else:
        logging.error("Invalid mode. Choose 1 or 2.")



if __name__ == "__main__":
    main()
