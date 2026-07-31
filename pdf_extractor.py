import re
import pypdf
import pdfplumber

# Comprehensive list of Newspaper codes
KNOWN_NEWSPAPERS = ['EBT', 'WSJ', 'CAP', 'NYT', 'SFC', 'UST', 'WLD', 'STD', 'LAT', 'FT', 'IBD', 'BAR', 'TVB']

STREET_SUFFIXES = (
    # Standard English suffixes & abbreviations
    'ALY', 'ALLEY', 'AVE', 'AVENUE', 'BLVD', 'BOULEVARD', 'CIR', 'CIRCLE', 'CRCL',
    'CT', 'COURT', 'CV', 'COVE', 'DR', 'DRIVE', 'EXPY', 'EXPWY', 'EXPRESSWAY', 
    'GLN', 'GLEN', 'HL', 'HILL', 'HWY', 'HIGHWAY', 'KNL', 'KNOLL', 'KNLS', 'KNOLLS',
    'LN', 'LANE', 'LOOP', 'PASS', 'PATH', 'PKWY', 'PARKWAY', 'PL', 'PLACE', 
    'PLZ', 'PLAZA', 'PT', 'POINT', 'RD', 'ROAD', 'RDG', 'RIDGE', 'RUN', 'SQ', 'SQUARE',
    'ST', 'STREET', 'TER', 'TERRACE', 'TRL', 'TRAIL', 'TRK', 'TRACK', 'VW', 'VIEW',
    'VIS', 'VISTA', 'VLY', 'VALLEY', 'WALK', 'WAY', 'WY', 'XING', 'CROSSING',
    
    # Spanish/Regional terms very common in California (especially Contra Costa)
    'AVENIDA', 'CALLE', 'CAMINO', 'CORTE', 'PASEO', 'VIA', 'VEREDA', 'VALLE'
)

STREET_PREFIXES = (
    'AVENIDA', 'CALLE', 'CAMINO', 'CORTE', 'PASEO', 'VIA', 'VEREDA', 'VALLE',
    'EL', 'LA', 'LOS', 'LAS', 'SAN', 'SANTA', 'DEL'
)

NAKED_STREET_NAMES = (
    'BROADWAY', 'ALAMEDA', 'EMBARCADERO', 'ESCOBAR', 'MARINA', 'VILLA', 'FRONT', 'MAIN'
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
            
        # 1. Test if line is a street header (e.g., "ARBOLADO DR", "PERRA WAY", "CORTE DIABLO")
        if not re.match(r'^\d+', line):
            has_suffix = tokens[-1] in STREET_SUFFIXES or tokens[-1] in NAKED_STREET_NAMES
            has_prefix = tokens[0] in STREET_PREFIXES
            if has_suffix or has_prefix:
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
                        if not re.match(r'^\d+[A-Z]$', token_upper):
                            addr_words.append(token)
                            
            if addr_words:
                street_part = " ".join(addr_words)
                if any(street_part.upper().endswith(s) for s in STREET_SUFFIXES):
                    full_addr = f"{num} {street_part}".strip().title()
                else:
                    full_addr = f"{num} {street_part} {current_street}".strip().title()
            elif current_street:
                full_addr = f"{num} {current_street}".strip().title()
            else:
                continue
                
            if full_addr not in address_papers:
                address_papers[full_addr] = set()
            address_papers[full_addr].update(detected_papers)

    return address_papers

def format_parsed_addresses(parsed):
    # Mandatory address removed
        
    items = []
    for raw_addr, papers in parsed.items():
        items.append({
            "raw_address": raw_addr,
            "newspapers": sorted(list(papers))
        })
    return items

def extract_addresses_from_pdf_stream(streams):
    """
    Extracts addresses and newspapers from a list of PDF file-like streams using pdfplumber visually or pypdf.
    """
    if not isinstance(streams, list):
        streams = [streams]
        
    address_papers = {}
    
    for stream in streams:
        if hasattr(stream, 'seek'):
            stream.seek(0)
            
        use_visual = False
        try:
            with pdfplumber.open(stream) as pdf:
                # Check first 2 pages for white text to determine if we can use visual extraction
                for page in pdf.pages[:2]:
                    words = page.extract_words(extra_attrs=['non_stroking_color'])
                    if any(w.get('non_stroking_color') == (1.0, 1.0, 1.0) for w in words):
                        use_visual = True
                        break
        except Exception:
            pass # Fallback to pypdf if pdfplumber fails

        if hasattr(stream, 'seek'):
            stream.seek(0)

        if use_visual:
            with pdfplumber.open(stream) as pdf:
                for page in pdf.pages:
                    words = page.extract_words(extra_attrs=['fontname', 'size', 'non_stroking_color'])
                    
                    header_words = [w for w in words if w.get('non_stroking_color') == (1.0, 1.0, 1.0)]
                    address_words = [w for w in words if w.get('non_stroking_color') != (1.0, 1.0, 1.0)]
                    
                    def group_words_to_lines(word_list, col_width):
                        lines = []
                        # Bucket by column first
                        columns = {0: [], 1: [], 2: [], 3: [], 4: []}
                        for w in word_list:
                            c = int(w['x0'] // col_width)
                            if c not in columns:
                                columns[c] = []
                            columns[c].append(w)
                            
                        for c, c_words in columns.items():
                            c_words.sort(key=lambda w: (round(w['top'] / 4) * 4, w['x0']))
                            if not c_words: continue
                            
                            current_line = [c_words[0]]
                            for w in c_words[1:]:
                                prev = current_line[-1]
                                if abs(w['top'] - prev['top']) < 3.5 and (w['x0'] - prev['x1']) < 250:
                                    current_line.append(w)
                                else:
                                    lines.append(current_line)
                                    current_line = [w]
                            if current_line:
                                lines.append(current_line)
                                
                        result = []
                        for line in lines:
                            text = ' '.join(w['text'] for w in line)
                            x0 = min(w['x0'] for w in line)
                            top = min(w['top'] for w in line)
                            bottom = max(w['bottom'] for w in line)
                            result.append({'text': text, 'x0': x0, 'top': top, 'bottom': bottom})
                        return result

                    col_width = 175.0
                    headers = group_words_to_lines(header_words, col_width)
                    addresses = group_words_to_lines(address_words, col_width)
                    
                    for addr in addresses:
                        addr_col = int(addr['x0'] // col_width)
                        valid_headers = [h for h in headers if int(h['x0'] // col_width) == addr_col and h['bottom'] <= addr['top'] + 5]
                        
                        if valid_headers:
                            best_header = max(valid_headers, key=lambda h: h['top'])
                            
                            match = re.match(r'^(\d+[\w\-]*)\s*(.*)', addr['text'], re.IGNORECASE)
                            if match:
                                num = match.group(1)
                                rest = match.group(2)
                                
                                rest_tokens = rest.split()
                                detected_papers = set()
                                addr_words = []
                                
                                for token in rest_tokens:
                                    token_upper = token.upper()
                                    if token_upper in KNOWN_NEWSPAPERS:
                                        detected_papers.add(token_upper)
                                    elif any(token_upper.endswith(s) or token_upper in STREET_SUFFIXES for s in STREET_SUFFIXES) or not detected_papers:
                                        if not token.isdigit() and not re.match(r'^\d+[A-Z]?$', token_upper):
                                            if not re.match(r'^\d+[A-Z]$', token_upper):
                                                addr_words.append(token)
                                                
                                street_part = " ".join(addr_words)
                                if street_part and any(street_part.upper().endswith(s) for s in STREET_SUFFIXES):
                                    full_addr = f"{num} {street_part}".strip().title()
                                else:
                                    full_addr = f"{num} {street_part} {best_header['text']}".strip().title()
                                    
                                full_addr = " ".join(full_addr.split())
                                
                                if full_addr not in address_papers:
                                    address_papers[full_addr] = set()
                                address_papers[full_addr].update(detected_papers)
        else:
            # Fallback strategy using layout extraction and text parsing
            full_text = ""
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
                        lines = txt.split('\n')
                        max_width = max((len(line) for line in lines), default=0)
                        col_width = (max_width // 3) + 1 if max_width > 0 else 30
                        
                        col1, col2, col3 = [], [], []
                        for line in lines:
                            c1 = line[0:col_width].strip() if len(line) > 0 else ""
                            c2 = line[col_width:col_width*2].strip() if len(line) > col_width else ""
                            c3 = line[col_width*2:].strip() if len(line) > col_width*2 else ""
                            if c1: col1.append(c1)
                            if c2: col2.append(c2)
                            if c3: col3.append(c3)
                        full_text += "\n".join(col1) + "\n"
                        full_text += "\n".join(col2) + "\n"
                        full_text += "\n".join(col3) + "\n"
                    else:
                        full_text += txt + "\n"
                
            parsed = parse_pdf_text(full_text)
            for addr, papers in parsed.items():
                if addr not in address_papers:
                    address_papers[addr] = set()
                address_papers[addr].update(papers)
                
    return format_parsed_addresses(address_papers)
