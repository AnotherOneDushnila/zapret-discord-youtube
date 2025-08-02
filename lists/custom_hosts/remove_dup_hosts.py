import os



priority_substrings = [
    "yt",
    "youtu",
    "google",
    "discord",
    "cloudflare",
    "riot",
    "valorant",
    "easyanticheat",
    "launcher"
]


def find_file(filename: str, max_depth: int = 2) -> str:
    current_dir = os.path.abspath(os.curdir)
    for _ in range(max_depth):
        candidate = os.path.join(current_dir, filename)
        if os.path.isfile(candidate):
            return candidate
        current_dir = os.path.dirname(current_dir)
    raise FileNotFoundError(f"File '{filename}' not found within {max_depth} directory levels upward.")


def sort_key(line: str) -> tuple:
    for index, substring in enumerate(priority_substrings):
        if substring in line:
            return (index, line)
    return (len(priority_substrings), line)


def rem_dup(filename: str) -> None:
    
    try:
        file = find_file(filename)
    except FileNotFoundError as e:
        print(e)
        return
    
    with open(file, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()


    unique_lines = list(set(lines))
    diff = len(lines) - len(unique_lines)

    if diff > 0:
        print("Duplicates found, removing..")
        unique_lines.sort(key=sort_key)
        with open(file, "w", encoding="utf-8") as f:
            for line in unique_lines:
                if line.strip():  
                    f.write(line + "\n")
        if diff > 1:
            print(f"{diff} duplicates were successfully deleted!")
        else:
            print("1 duplicate was successfully deleted!")
    else:
        print("No duplicates found")


def main() -> None:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    filename = input("Enter the filename to remove duplicates from (default: 'hosts.txt'): ").strip()
    rem_dup(filename)


if __name__ == "__main__":
    main()