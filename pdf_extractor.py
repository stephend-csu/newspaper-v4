import re
import pypdf

# Default/Known Newspaper codes
KNOWN_NEWSPAPERS = ['EBT', 'WSJ', 'NYT', 'SFC', 'UST', 'WLD', 'STD', 'LAT', 'FT']

def parse_pdf_text(text: str):
    """
    Parses text extracted from a delivery route PDF.
    Handles structure like:
      PERRA WAY
      3104  EBT
      3104  SFC
      3104  WSJ
    Or line formats like:
      3104 Perra Way EBT SFC WSJ
    Returns a dict mapping normalized street address (without city) to a set of newspaper tags.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    
    address_papers = {}  # e.g., "3104 PERRA WAY": {"EBT", "SFC", "WSJ"}
    current_street = ""
    
    # Common street suffix keywords
    street_suffixes = (
        'WAY', 'RD', 'ROAD', 'DR', 'DRIVE', 'CT', 'COURT', 'LN', 'LANE',
        'AVE', 'AVENUE', 'BLVD', 'BOULEVARD', 'CIR', 'CIRCLE', 'PL', 'PLACE',
        'CORTE', 'CAMINO', 'WAY', 'ST', 'STREET', 'HWY', 'PATH', 'TERRACE', 'TER'
    )
    
    for line in lines:
        tokens = line.upper().split()
        
        # Test if line is a pure street header
        if not re.match(r'^\d+', line) and any(tokens[-1] == suff or (len(tokens) > 1 and tokens[-1] in street_suffixes) for suff in street_suffixes):
            current_street = line.strip()
            continue
            
        # Check if line starts with a house number e.g. "3104 EBT" or "3104  SFC"
        match = re.match(r'^(\d+[\w\-]*)\s+(.+)$', line, re.IGNORECASE)
        if match:
            num, rest = match.groups()
            rest_tokens = rest.strip().split()
            
            # Check if rest consists only of newspaper codes
            is_only_papers = all(t.upper() in KNOWN_NEWSPAPERS or re.match(r'^[A-Z]{2,4}$', t.upper()) for t in rest_tokens)
            
            if is_only_papers and current_street:
                full_addr = f"{num} {current_street}".strip().title()
                if full_addr not in address_papers:
                    address_papers[full_addr] = set()
                for paper in rest_tokens:
                    address_papers[full_addr].add(paper.upper())
            else:
                paper_list = []
                addr_words = []
                for word in rest_tokens:
                    if word.upper() in KNOWN_NEWSPAPERS or (len(word) <= 4 and word.isupper()):
                        paper_list.append(word.upper())
                    else:
                        addr_words.append(word)
                
                if addr_words:
                    street_part = " ".join(addr_words)
                    full_addr = f"{num} {street_part}".strip().title()
                elif current_street:
                    full_addr = f"{num} {current_street}".strip().title()
                else:
                    continue
                
                if full_addr not in address_papers:
                    address_papers[full_addr] = set()
                for p in paper_list:
                    address_papers[full_addr].add(p)

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
        parsed["923 Pacific Ct"] = {"EBT"} # Default tag if not in PDF
        
    items = []
    for raw_addr, papers in parsed.items():
        items.append({
            "raw_address": raw_addr,
            "newspapers": sorted(list(papers))
        })
        
    return items
