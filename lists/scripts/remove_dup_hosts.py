import os, logging, tldextract
from typing import Tuple, List
from service import Service



service = Service("dup-hosts")
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')


priority_substrings = [
    "yt",
    "youtu",
    "google",
    "discord",
    "t",
    "tel",
    "cloudflare",
    "riot",
    "valorant",
    "easyanticheat",
    "launcher"
]


@service.log_file_change
def remove_duplicates(filepath: str, only_main: bool) -> None:
    def sort_key(line: str) -> Tuple[int, str]:
        for index, substring in enumerate(priority_substrings):
            if substring in line:
                return (index, line)
        return (len(priority_substrings), line)
    
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    
    if only_main:
        lines = only_main_dom(lines)

    unique = list(set(lines))

    if len(lines) - len(unique) > 0:
        unique.sort(key=sort_key)
        with open(filepath, "w", encoding="utf-8") as f:
            for line in unique:
                if line.strip():  
                    f.write(line + "\n")
    else:
        return None


def only_main_dom(domains: List[str]) -> list:
    res = []

    for dom in domains:
        ext = tldextract.extract(dom)
        res.append(f"{ext.domain}.{ext.suffix}")
        
    return res


def main() -> None:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    args = service.argparse().parse_args()
    filepath = service.find_file(args.filename)
    only_main = args.only_main
    remove_duplicates(filepath, only_main)


if __name__ == "__main__":
    main()