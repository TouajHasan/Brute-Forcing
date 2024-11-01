import os
import argparse
import requests
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import re

# ASCII Banner
banner = """
                            ████████╗ ██████╗ ██╗   ██╗ █████╗       ██╗     
                            ╚══██╔══╝██╔═══██╗██║   ██║██╔══██╗      ██║     
                               ██║   ██║   ██║██║   ██║███████║      ██║     
                               ██║   ██║   ██║██║   ██║██╔══██║ ██   ██║     
                               ██║   ╚██████╔╝╚██████╔╝██║  ██║ ╚█████╔╝     
                               ╚═╝    ╚═════╝  ╚═════╝ ╚═╝  ╚═╝  ╚════╝  
           
                                                Version 1.0
"""

print(banner)

def is_valid_url(url):
    """Validate URL format."""
    regex = re.compile(
        r'^(https?://)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,6}(:[0-9]{1,5})?(/.*)?$'
    )
    return re.match(regex, url)

def save_to_file(url, status_code, output_file):
    """Save found URL to the output file."""
    with open(output_file, "a") as file:
        file.write(f"[{status_code}] {url}\n")

def save_progress(progress_file, completed_words):
    """Save the list of completed words to a file."""
    with open(progress_file, "w") as file:
        for word in completed_words:
            file.write(f"{word}\n")

def load_progress(progress_file):
    """Load the list of completed words from a file."""
    if os.path.exists(progress_file):
        with open(progress_file, "r") as file:
            return {line.strip() for line in file}
    return set()

def request_url(url, match_codes, output_file, found_urls, retries=3):
    """Send a GET request to the URL."""
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=10)  # Timeout set to 10 seconds
            if response.status_code in match_codes and url not in found_urls:
                found_urls.add(url)  # Add to set for uniqueness
                print(f"\033[92m[{response.status_code}] {url}\033[0m")  # Print in green color
                save_to_file(url, response.status_code, output_file)
            return  # Exit the function if successful
        except requests.Timeout:
            # Uncomment the line below if you want to log timeouts instead of printing
            # print(f"Timeout occurred for {url}. Retrying ({attempt + 1}/{retries})...")
            continue  # Ignore timeouts and continue with the next attempt
        except requests.RequestException:
            # Ignore other request exceptions and continue with the next attempt
            continue
    # If you want to show a message when all attempts fail, uncomment the line below
    # print(f"Failed to retrieve {url} after {retries} attempts.")

def brute_force(base_url, wordlist, threads, match_codes, output_dir, progress_file, resume=False, suffixes=None, case=None, log_file=None):
    """Perform directory brute-force with multithreading and progress tracking."""
    
    # Create output directory based on the domain name
    domain = base_url.split("//")[-1].split("/")[0]  # Get domain name from URL
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(output_dir, exist_ok=True)  # Create directory if it doesn't exist
    output_file = os.path.join(output_dir, f"output_{timestamp}.txt")  # Create timestamped output file

    found_urls = set()  # Set to store unique URLs
    completed_words = load_progress(progress_file) if resume else set()  # Load progress if resume is enabled
    
    to_scan = []
    for word in wordlist:
        word = word.strip()
        if word not in completed_words:
            if suffixes:  # If suffixes are provided
                for suffix in suffixes:
                    to_scan.append(f"{word}{suffix}")
            else:
                to_scan.append(word)
    
    if case == 'uppercase':
        to_scan = [word.upper() for word in to_scan]
    elif case == 'lowercase':
        to_scan = [word.lower() for word in to_scan]
    elif case == 'capital':
        to_scan = [word.capitalize() for word in to_scan]
    
    with ThreadPoolExecutor(max_workers=threads) as executor:
        for word in to_scan:
            completed_words.add(word)  # Track each completed word
            target_url = base_url.replace("THS", word)
            print(f"\rBruteforcing: {target_url}...", end="")  # Print current URL in single line
            executor.submit(request_url, target_url, match_codes, output_file, found_urls)
            save_progress(progress_file, completed_words)  # Save progress after each word

    if log_file:
        with open(log_file, "a") as log:
            log.write(f"Brute-forcing completed for {base_url} at {datetime.now()}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Directory brute-forcing tool similar to Dirsearch with FFUF-style FUZZ placement.")
    parser.add_argument("-u", "--url", required=True, help="Target URL (use 'FUZZ' to specify brute-force position)")
    parser.add_argument("-w", "--wordlist", required=True, help="Path to wordlist file")
    parser.add_argument("-t", "--threads", type=int, default=30, help="Number of threads (default: 30)")
    
    # Default status codes updated to include a comprehensive list
    default_match_codes = "200,204,301,302,307,403,500,502,503"
    parser.add_argument("-mc", "--match-codes", default=default_match_codes, help="Comma-separated status codes to match (default: 200,204,301,302,307,403,500,502,503)")
    parser.add_argument("--log", help="Log file path")
    parser.add_argument("-r", "--resume", action="store_true", help="Resume scan from the last completed word")
    parser.add_argument("--crawl", action="store_true", help="Crawl for new paths in responses")
    parser.add_argument("--suffixes", type=str, help="Add custom suffixes to all wordlist entries, ignore directories (separated by commas)")
    parser.add_argument("-U", "--uppercase", action="store_true", help="Uppercase wordlist")
    parser.add_argument("-L", "--lowercase", action="store_true", help="Lowercase wordlist")
    parser.add_argument("-C", "--capital", action="store_true", help="Capital wordlist")
    parser.add_argument("-R", "--recursive", action="store_true", help="Brute-force recursively")  # Changed this to avoid conflict

    args = parser.parse_args()

    # Validate URL format
    if not is_valid_url(args.url):
        print("Invalid URL format. Please try again.")
        exit(1)

    # Parse match codes
    match_codes = [int(code.strip()) for code in args.match_codes.split(",")]

    # Load wordlist with fallback encoding
    try:
        with open(args.wordlist, "r", encoding='utf-8') as f:
            wordlist = f.readlines()
    except UnicodeDecodeError:
        try:
            with open(args.wordlist, "r", encoding='latin1') as f:
                wordlist = f.readlines()
        except FileNotFoundError:
            print("Wordlist file not found. Please check the path and try again.")
            exit(1)
        except Exception as e:
            print(f"Error reading the wordlist file with Latin-1 encoding: {e}")
            exit(1)
    except FileNotFoundError:
        print("Wordlist file not found. Please check the path and try again.")
        exit(1)
    except Exception as e:
        print(f"Error reading the wordlist file: {e}")
        exit(1)

    # Handle suffixes
    suffixes = args.suffixes.split(",") if args.suffixes else None

    # Determine case transformation
    case = None
    if args.uppercase:
        case = 'uppercase'
    elif args.lowercase:
        case = 'lowercase'
    elif args.capital:
        case = 'capital'

    # Create output directory based on the domain name
    domain = args.url.split("//")[-1].split("/")[0]  # Get domain name from URL
    output_dir = os.path.join(os.getcwd(), domain)  # Create output directory path

    brute_force(args.url, wordlist, args.threads, match_codes, output_dir, "scan_progress.txt", args.resume, suffixes, case, args.log)
    print(f"\nBrute-forcing completed. Results saved in '{output_dir}'.")
