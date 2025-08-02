# Author: V3nilla
# Original repo: https://github.com/V3nilla/IPSets-For-Bypass-in-Russia/blob/main/CIDR%20Manager/cidr_manager.py
# Modified by: AnotherOneDushnila
import os, logging, ipaddress



logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')


def find_file(filename: str, max_depth: int = 2) -> str:
    current_dir = os.path.abspath(os.curdir)
    for _ in range(max_depth):
        candidate = os.path.join(current_dir, filename)
        if os.path.isfile(candidate):
            return candidate
        current_dir = os.path.dirname(current_dir)
    raise FileNotFoundError(f"File '{filename}' not found within {max_depth} directory levels upward.")


def aggergate_subnets(filename: str) -> None:
    try:
        input_file = find_file(filename)
    except FileNotFoundError as e:
        print(e)
        return
    
    output_file = os.path.join(
        os.path.dirname(input_file), 
        f"cleaned_and_aggregated_{os.path.basename(input_file)}"
        )

    with open(input_file) as file:
        raw_lines = [line.strip() for line in file if line.strip()]
    
    logging.info(f"Loaded {len(raw_lines)} entries from {input_file}")

    subnets = []
    seen = set()
    for line in raw_lines:
        try:
            net = ipaddress.IPv4Network(line, strict=False)
            if net in seen:
                logging.warning(f"Duplicate found and skipped: {net}")
            else:
                seen.add(net)
                subnets.append(net)
        except ValueError as e:
            logging.error(f"Invalid subnet '{line}': {e}")

    aggregated = list(ipaddress.collapse_addresses(subnets))
    aggregated.sort(key=lambda net: int(net.network_address))

    with open(output_file, "w") as out_file:
        for net in aggregated:
            out_file.write(str(net) + "\n")

    logging.info(f"Aggregated list written to {output_file} ({len(aggregated)} entries)")


def main() -> None:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    filename = input("Enter the filename to process (e.g., 'subnets.txt'): ").strip()
    aggergate_subnets(filename)
    

if __name__ == "__main__":
    main()