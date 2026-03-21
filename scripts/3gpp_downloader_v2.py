import os
import zipfile
import requests
from bs4 import BeautifulSoup
import win32com.client
import argparse
import urllib.parse
import re

def setup_directory(download_dir):
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
    print(f"[*] Directory created/ready: {download_dir}")

def get_document_links(base_url, work_item):
    print(f"[*] Searching whatthespec.net for '{work_item}'...")
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(base_url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    links = []
    # WhatTheSpec typically embeds links directly to 3GPP FTP
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        # Look for standard 3GPP document formats
        if href.endswith('.zip') or href.endswith('.doc') or href.endswith('.docx'):
            if href not in links:
                links.append(href)
                
    print(f"[*] Found {len(links)} documents related to {work_item}.")
    return links

def download_file(url, download_dir):
    local_filename = os.path.join(download_dir, url.split('/')[-1])
    if os.path.exists(local_filename):
        print(f"    -> Already downloaded: {local_filename}")
        return local_filename
        
    print(f"    -> Downloading {url} ...")
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return local_filename

def extract_zip(zip_path, extract_folder):
    print(f"    -> Extracting {zip_path} ...")
    if not os.path.exists(extract_folder):
        os.makedirs(extract_folder)
        
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_folder)
        os.remove(zip_path) # Clean up zip after extracting
    except Exception as e:
        print(f"    [!] Error extracting {zip_path}: {e}")


def convert_office_to_pdf(download_dir):
    abs_folder_path = os.path.abspath(download_dir)
    files = os.listdir(abs_folder_path)
    
    # Initialize Apps as None
    word_app = None
    ppt_app = None

    print(f"[*] Scanning for Office documents in: {abs_folder_path}")

    try:
        for filename in files:
            if filename.startswith('~$'): continue # Skip temp files
            
            ext = os.path.splitext(filename)[1].lower()
            in_file = os.path.join(abs_folder_path, filename)
            out_file = os.path.join(abs_folder_path, os.path.splitext(filename)[0] + ".pdf")

            # Skip if PDF already exists
            if os.path.exists(out_file):
                continue

            # --- WORD CONVERSION (.doc, .docx) ---
            if ext in ['.doc', '.docx']:
                if not word_app:
                    word_app = win32com.client.DispatchEx("Word.Application")
                    word_app.Visible = False
                    word_app.DisplayAlerts = 0
                
                print(f"  -> [Word] Converting: {filename}")
                doc = word_app.Documents.Open(in_file, ReadOnly=True)
                doc.SaveAs(out_file, FileFormat=17) # 17 = wdFormatPDF
                doc.Close(0)

            # --- POWERPOINT CONVERSION (.ppt, .pptx) ---
            elif ext in ['.ppt', '.pptx']:
                if not ppt_app:
                    ppt_app = win32com.client.DispatchEx("PowerPoint.Application")
                
                print(f"  -> [PPT]  Converting: {filename}")
                presentation = ppt_app.Presentations.Open(in_file, ReadOnly=True, WithWindow=False)
                presentation.SaveAs(out_file, 32) 
                presentation.Close()

    except Exception as e:
        print(f"[!] Error: {e}")
        
    finally:
        # Gracefully shut down the background engines
        if word_app:
            word_app.Quit()
            print("[*] Word engine closed.")
        if ppt_app:
            ppt_app.Quit()
            print("[*] PowerPoint engine closed.")
        print("[*] Conversion process finished.")

def parse_arguments():
    parser = argparse.ArgumentParser(description="3GPP Document Downloader")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--spec', type=str, help="3GPP Spec ID (e.g., 38.331)")
    group.add_argument('--wi', type=str, help="Work Item (e.g., eNS)")
    
    parser.add_argument('--title', type=str, help="Title for WI/SI search")
    
    return parser.parse_args()

def main():
    args = parse_arguments()
    
    # 1. Evaluate workflow inputs
    if args.spec:
        work_item = args.spec
        base_url = f"https://whatthespec.net/3gpp/spec.php?q={args.spec}"
        
    elif args.wi:
        if not args.title:
            print("Error: --title is required when using --wi")
            return
            
        # Encode spaces to '+' for URL safety
        safe_title = urllib.parse.quote_plus(args.title)
        safe_wid = urllib.parse.quote_plus(args.wi)
        base_url = f"https://whatthespec.net/3gpp/tdoc.php?name=&title={safe_title}&type=&source=&spec=&wid={safe_wid}&rel=&meeting=&status=&searchtdocs=search"
        
        # Build WORK_ITEM string by removing whitespace from the title
        clean_title = re.sub(r'\s+', '', args.title)
        work_item = f"WI_{args.wi}_TITLE_{clean_title}"
    else:
        print("Invalid workflow. Please provide either --spec or --wi and --title.")
        return
        
    download_dir = f"./3gpp/{work_item}_docs"
    
    # 2. Setup directory
    setup_directory(download_dir)
    
    # 3. Find Links
    links = get_document_links(base_url, work_item)
    if not links:
        print("No downloadable documents found. Exiting.")
        return

    # 4. Download and Extract
    for link in links:
        file_path = download_file(link, download_dir)
        if file_path.endswith('.zip'):
            extract_zip(file_path, download_dir)
            
    # 5. Convert all extracted Word docs to PDF
    convert_office_to_pdf(download_dir)
    print(f"[*] Automation complete! All PDFs are saved in the '{download_dir}' folder.")

if __name__ == "__main__":
    main()