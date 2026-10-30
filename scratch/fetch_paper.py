import httpx
from pathlib import Path
from pypdf import PdfReader

url = "https://journalijecc.com/index.php/IJECC/article/download/5028/10645/7846"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

out_dir = Path("scratch")
out_dir.mkdir(exist_ok=True)
pdf_path = out_dir / "kumar_2025_sugarcane_wilt.pdf"

print("Downloading PDF...")
with httpx.Client(follow_redirects=True, timeout=30.0, headers=headers) as client:
    resp = client.get(url)
    print("Status code:", resp.status_code)
    if resp.status_code == 200:
        pdf_path.write_bytes(resp.content)
        print(f"Saved {len(resp.content)} bytes to {pdf_path}")
        
        reader = PdfReader(pdf_path)
        print(f"Total pages: {len(reader.pages)}")
        all_text = ""
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            all_text += f"\n--- PAGE {i+1} ---\n" + text
        
        (out_dir / "kumar_2025_text.txt").write_text(all_text, encoding="utf-8")
        print("Extracted text saved to scratch/kumar_2025_text.txt")
    else:
        print("Failed to download, body:", resp.text[:300])

