import re

filepath = r"c:\Users\stardust\Desktop\newspaper-v4-main\pdf_extractor.py"
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace len(token) > 1 condition
old_cond = "if len(token) > 1 and not re.match(r'^\\d+[A-Z]$', token_upper):"
new_cond = "if not re.match(r'^\\d+[A-Z]$', token_upper):"
content = content.replace(old_cond, new_cond)

# Replace address assembly
old_assembly = """            if addr_words:
                street_part = " ".join(addr_words)
                full_addr = f"{num} {street_part}".strip().title()
            elif current_street:
                full_addr = f"{num} {current_street}".strip().title()"""

new_assembly = """            if addr_words:
                street_part = " ".join(addr_words)
                if any(street_part.upper().endswith(s) for s in STREET_SUFFIXES):
                    full_addr = f"{num} {street_part}".strip().title()
                else:
                    full_addr = f"{num} {street_part} {current_street}".strip().title()
            elif current_street:
                full_addr = f"{num} {current_street}".strip().title()"""
content = content.replace(old_assembly, new_assembly)

# Replace extract_addresses_from_pdf_stream logic
old_extract = """def extract_addresses_from_pdf_stream(stream):
    \"\"\"
    Extracts addresses and newspapers from a PDF file-like stream using pypdf.
    \"\"\"
    reader = pypdf.PdfReader(stream)
    full_text = ""
    for page in reader.pages:
        txt = page.extract_text()
        if txt:
            full_text += txt + "\\n\"\"\"

new_extract = """def extract_addresses_from_pdf_stream(stream):
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
                full_text += txt + "\\n\"\"\"
content = content.replace(old_extract, new_extract)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated pdf_extractor.py")
