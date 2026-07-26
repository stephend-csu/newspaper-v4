import re
import pypdf

# Comprehensive list of Newspaper codes
KNOWN_NEWSPAPERS = ['EBT', 'WSJ', 'CAP', 'NYT', 'SFC', 'UST', 'WLD', 'STD', 'LAT', 'FT', 'IBD', 'BAR']

STREET_SUFFIXES = (
    'WAY', 'RD', 'ROAD', 'DR', 'DRIVE', 'CT', 'COURT', 'LN', 'LANE',
    'AVE', 'AVENUE', 'BLVD', 'BOULEVARD', 'CIR', 'CIRCLE', 'PL', 'PLACE',
    'CORTE', 'CAMINO', 'WAY', 'ST', 'STREET', 'HWY', 'PATH', 'TERRACE', 'TER', 'PKWY', 'PARKWAY'
)

def parse_pdf_text(text: str):
    """
    Parses text extracted from a delivery route PDF.
    Handles headers like:
      ARBOLADO DR
      91 EBT 7D 1
      93 EBT 7D 1
      155 EBT 7D 1
      172 EBT 7D 1
    Extracts street address (e.g. 91 Arbolado Dr) and newspapers (EBT, WSJ, CAP, etc.).
    Discards non-newspaper route markers like '7D', '1', etc.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    
    address_papers = {}  # e.g., "91 Arbolado Dr": {"EBT"}
    current_street = ""
    
    for line in lines:
        tokens = line.upper().split()
        if not tokens:
            continue
            
        # 1. Test if line is a street header (e.g., "ARBOLADO DR", "PERRA WAY", "PEAK CT")
        if not re.match(r'^\d+', line) and any(tokens[-1] == suff or (len(tokens) > 1 and tokens[-1] in STREET_SUFFIXES) for suff in STREET_SUFFIXES):
            current_street = line.strip()
            continue
            
        # 2. Check if line starts with a house number e.g. "91 EBT 7D 1" or "3104 Perra Way EBT WSJ"
        match = re.match(r'^(\d+[\w\-]*)\s+(.+)$', line, re.IGNORECASE)
        if match:
            num, rest = match.groups()
            rest_tokens = rest.strip().split()
            
            detected_papers = set()
            addr_words = []
            
            for token in rest_tokens:
                token_upper = token.upper()
                if token_upper in KNOWN_NEWSPAPERS:
                    detected_papers.add(token_upper)
                elif any(token_upper.endswith(s) or token_upper in STREET_SUFFIXES for s in STREET_SUFFIXES) or not detected_papers:
                    # Token is part of street name if no newspapers detected yet and it's alphabetic
                    if not token.isdigit() and not re.match(r'^\d+[A-Z]?$', token_upper):
                        # Avoid treating route codes like 7D or 1 as street names
                        if len(token) > 1 and not re.match(r'^\d+[A-Z]$', token_upper):
                            addr_words.append(token)
                            
            if addr_words:
                street_part = " ".join(addr_words)
                full_addr = f"{num} {street_part}".strip().title()
            elif current_street:
                full_addr = f"{num} {current_street}".strip().title()
            else:
                continue
                
            if full_addr not in address_papers:
                address_papers[full_addr] = set()
            address_papers[full_addr].update(detected_papers)

    return address_papers

def extract_addresses_from_pdf_stream(stream):
    """
    Extracts addresses and newspapers from a PDF file-like stream using pypdf.
    """
    reader = pypdf.PdfReader(stream)
    full_text = ""
    for page in reader.pages:
        txt = page.extract_text()
        if txt:
            full_text += txt + "\n"
            
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
        
    return items
