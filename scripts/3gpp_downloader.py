import os
import zipfile
import requests
from bs4 import BeautifulSoup
import os
import win32com.client

# --- CONFIGURATION ---
WORK_ITEM = "Mobility_NR_NTN_enh"
BASE_URL = f"https://whatthespec.net/3gpp/tdoc.php?name=&title=Mobility&type=&source=&spec=&wid=NR_NTN_enh&rel=&meeting=&status=&searchtdocs=search"

# WORK_ITEM ="38.331"
# BASE_URL = "https://whatthespec.net/3gpp/spec.php?q=38.331"
DOWNLOAD_DIR = f"./3gpp/{WORK_ITEM}_docs"

def setup_directory():
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
    print(f"[*] Directory created/ready: {DOWNLOAD_DIR}")

def get_document_links():
    print(f"[*] Searching whatthespec.net for '{WORK_ITEM}'...")
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(BASE_URL, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    links = []
    # WhatTheSpec typically embeds links directly to 3GPP FTP
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        # Look for standard 3GPP document formats
        if href.endswith('.zip') or href.endswith('.doc') or href.endswith('.docx'):
            if href not in links:
                links.append(href)
                
    print(f"[*] Found {len(links)} documents related to {WORK_ITEM}.")
    return links

def download_file(url):
    local_filename = os.path.join(DOWNLOAD_DIR, url.split('/')[-1])
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

def extract_zip(zip_path):
    print(f"    -> Extracting {zip_path} ...")
    extract_folder = DOWNLOAD_DIR
    if not os.path.exists(extract_folder):
        os.makedirs(extract_folder)
        
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_folder)
        os.remove(zip_path) # Clean up zip after extracting
    except Exception as e:
        print(f"    [!] Error extracting {zip_path}: {e}")


def convert_office_to_pdf():
    folder_path = DOWNLOAD_DIR
    abs_folder_path = os.path.abspath(folder_path)
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
                    # PowerPoint requires a slightly different way to hide the window
                
                print(f"  -> [PPT]  Converting: {filename}")
                # WithWindow=False makes it run in the background
                presentation = ppt_app.Presentations.Open(in_file, ReadOnly=True, WithWindow=False)
                # 32 = ppSaveAsPDF
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

def main():
    setup_directory()
    links = get_document_links()
    
    if not links:
        print("No downloadable documents found. Exiting.")
        return

    # 1. Download
    for link in links:
        file_path = download_file(link)
        # 2. Extract if it's a zip
        if file_path.endswith('.zip'):
            extract_zip(file_path)
            
    # 3. Convert all extracted Word docs to PDF
    # convert_office_to_pdf();
    # print(f"[*] Automation complete! All PDFs are saved in the '{DOWNLOAD_DIR}' folder.")

if __name__ == "__main__":
    main()