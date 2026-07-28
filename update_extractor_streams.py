import sys

filepath = r"c:\Users\stardust\Desktop\newspaper-v4-main\pdf_extractor.py"
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

old_extract = """def extract_addresses_from_pdf_stream(stream):
    \"\"\"
    Extracts addresses and newspapers from a PDF file-like stream using pypdf.
    \"\"\"
    reader = pypdf.PdfReader(stream)
    full_text = ""
    for page in reader.pages:
        try:
            txt = page.extract_text(extraction_mode="layout")
            is_layout = True
        except TypeError:
            txt = page.extract_text()
            is_layout = False
            
        if txt:
            if is_layout:
                col1, col2, col3 = [], [], []
                for line in txt.split('\\n'):
                    c1 = line[0:30].strip() if len(line) > 0 else ""
                    c2 = line[30:61].strip() if len(line) > 30 else ""
                    c3 = line[61:].strip() if len(line) > 61 else ""
                    if c1: col1.append(c1)
                    if c2: col2.append(c2)
                    if c3: col3.append(c3)
                full_text += "\\n".join(col1) + "\\n"
                full_text += "\\n".join(col2) + "\\n"
                full_text += "\\n".join(col3) + "\\n"
            else:
                full_text += txt + "\\n"
            
    parsed = parse_pdf_text(full_text)
    
    # Always include mandatory address: 923 Pacific Ct, Walnut Creek, CA
    mandatory_key = "923 Pacific Ct"
    found_mandatory = False
    for k in parsed:
        if "923 pacific" in k.lower():
            found_mandatory = True
            break
    if not found_mandatory:
        parsed["923 Pacific Ct"] = {"EBT"}
        
    items = []
    for raw_addr, papers in parsed.items():
        items.append({
            "raw_address": raw_addr,
            "newspapers": sorted(list(papers))
        })
        
    return items"""

new_extract = """def format_parsed_addresses(parsed):
    # Always include mandatory address: 923 Pacific Ct, Walnut Creek, CA
    found_mandatory = False
    for k in parsed:
        if "923 pacific" in k.lower():
            found_mandatory = True
            break
    if not found_mandatory:
        parsed["923 Pacific Ct"] = {"EBT"}
        
    items = []
    for raw_addr, papers in parsed.items():
        items.append({
            "raw_address": raw_addr,
            "newspapers": sorted(list(papers))
        })
    return items

def extract_addresses_from_pdf_stream(streams):
    \"\"\"
    Extracts addresses and newspapers from a list of PDF file-like streams using pypdf.
    \"\"\"
    if not isinstance(streams, list):
        streams = [streams]
        
    full_text = ""
    for stream in streams:
        reader = pypdf.PdfReader(stream)
        for page in reader.pages:
            try:
                txt = page.extract_text(extraction_mode="layout")
                is_layout = True
            except TypeError:
                txt = page.extract_text()
                is_layout = False
                
            if txt:
                if is_layout:
                    col1, col2, col3 = [], [], []
                    for line in txt.split('\\n'):
                        c1 = line[0:30].strip() if len(line) > 0 else ""
                        c2 = line[30:61].strip() if len(line) > 30 else ""
                        c3 = line[61:].strip() if len(line) > 61 else ""
                        if c1: col1.append(c1)
                        if c2: col2.append(c2)
                        if c3: col3.append(c3)
                    full_text += "\\n".join(col1) + "\\n"
                    full_text += "\\n".join(col2) + "\\n"
                    full_text += "\\n".join(col3) + "\\n"
                else:
                    full_text += txt + "\\n"
            
    parsed = parse_pdf_text(full_text)
    return format_parsed_addresses(parsed)"""

if old_extract in content:
    content = content.replace(old_extract, new_extract)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Success")
else:
    print("Could not find old extract text to replace!")
