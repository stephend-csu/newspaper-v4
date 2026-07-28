import os
from pdf_extractor import extract_addresses_from_pdf_stream

for pdf_name in ['sun.pdf', 'only1.pdf', 'mon726.pdf']:
    path = os.path.join(r"c:\Users\stardust\Desktop\newspaper-v4-main", pdf_name)
    print(f"\n{'='*50}\nTesting {pdf_name}\n{'='*50}")
    with open(path, 'rb') as f:
        results = extract_addresses_from_pdf_stream([f])
        for r in results:
            if "Spring" in r['raw_address'] or "SPRINGFIELD" in r['raw_address']:
                print(r)
        
        # print some random addresses to ensure it's parsing generally
        for r in results[:5]:
            print(r)
