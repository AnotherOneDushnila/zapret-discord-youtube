import os, subprocess, time
import ipaddress
import re



def get_ips(domain_list_path: str, os: str) -> str:
    try:
        with open(domain_list_path, "r", encoding="utf-8") as file:
            domains = [line.strip() for line in file if line.strip()]
        
        output = ""
        
        if os == "w":
            for domain in domains:
                result = subprocess.run(
                    ['powershell', '-Command', f"nslookup {domain}"],
                    capture_output=True, text=True, check=True
                )

                time.sleep(2)

                output += str(result.stdout)

            return output
        
        elif os in "ml":
            for domain in domains:
                result = subprocess.run(
                    ["nslookup", domain],
                    capture_output=True, text=True, check=True
                )

                time.sleep(2)

                output += str(result.stdout)

            return output
        
        else:
            raise ValueError("Invalid OS choice. Use 'w' for Windows, 'l' for Linux or 'm' for MacOS.")
       

    except subprocess.CalledProcessError as e:
        return f"Error occurred: {e}\nError log: {e.stderr}"


def log_formatter(log: str) -> None:
    excluded_ips = {'1.1.1.1', '8.8.8.8', '8.8.4.4'}

    ip_pattern = re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b')
    ips = sorted(
        (ip for ip in ip_pattern.findall(log) if ip not in excluded_ips),
        key=lambda x: list(map(int, x.split('.'))), reverse=True
    )

    ip_objects = [ipaddress.IPv4Address(ip) for ip in ips]
    cidrs = list(ipaddress.collapse_addresses(ip_objects))

    
    with open("rename-this-ipset.txt", "w", encoding="utf-8") as f:
        for cidr in sorted(cidrs, reverse=True):
            f.write(str(cidr) + "\n")

    print(f"Extracted {len(ips)} IPs into {len(cidrs)} CIDR blocks. Saved to rename-this-ipset.txt")


def main() -> None:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    os_check = input("Enter the first letter of name of your OS (Linux/Windows/MacOS): ").strip().lower()
    log = get_ips("blocked-hosts-rtk.txt", os_check)
    log_formatter(log)


if __name__ == "__main__":
    main()