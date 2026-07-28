import sys

filepath = r"c:\Users\stardust\Desktop\newspaper-v4-main\server.py"
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

old_import = "from pdf_extractor import extract_addresses_from_pdf_stream"
new_import = "from pdf_extractor import extract_addresses_from_pdf_stream, parse_pdf_text, format_parsed_addresses"
content = content.replace(old_import, new_import)

old_api_upload = """@app.route('/api/upload-pdf', methods=['POST'])
def api_upload_pdf():
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'No PDF file uploaded'}), 400
        
    file = request.files['pdf_file']
    if not file.filename:
        return jsonify({'error': 'Empty filename'}), 400
        
    try:
        extracted_items = extract_addresses_from_pdf_stream(file.stream)
        job_id = str(uuid.uuid4())
        JOB_STATUSES[job_id] = {'status': 'processing', 'message': 'PDF extracted. Starting geocoding...'}
        
        thread = threading.Thread(target=run_upload_geocoding_job, args=(job_id, extracted_items))
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'job_id': job_id})
    except Exception as e:
        print(f"Error processing PDF: {e}")
        return jsonify({'error': f"Failed to process PDF: {str(e)}"}), 500"""

new_api_upload = """@app.route('/api/upload-pdf', methods=['POST'])
def api_upload_pdf():
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'No PDF file uploaded'}), 400
        
    files = request.files.getlist('pdf_file')
    if not files or all(not f.filename for f in files):
        return jsonify({'error': 'Empty filename'}), 400
        
    try:
        streams = [f.stream for f in files if f.filename]
        extracted_items = extract_addresses_from_pdf_stream(streams)
        job_id = str(uuid.uuid4())
        JOB_STATUSES[job_id] = {'status': 'processing', 'message': 'PDF extracted. Starting geocoding...'}
        
        thread = threading.Thread(target=run_upload_geocoding_job, args=(job_id, extracted_items))
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'job_id': job_id})
    except Exception as e:
        print(f"Error processing PDF: {e}")
        return jsonify({'error': f"Failed to process PDF: {str(e)}"}), 500

@app.route('/api/upload-manual-addresses', methods=['POST'])
def api_upload_manual_addresses():
    data = request.get_json() or {}
    addresses_text = data.get('addresses', '')
    if not addresses_text.strip():
        return jsonify({'error': 'No addresses provided'}), 400
        
    try:
        parsed = {}
        for line in addresses_text.splitlines():
            line = line.strip()
            if line:
                parsed[line] = set()
                
        extracted_items = format_parsed_addresses(parsed)
        job_id = str(uuid.uuid4())
        JOB_STATUSES[job_id] = {'status': 'processing', 'message': 'Addresses parsed. Starting geocoding...'}
        
        thread = threading.Thread(target=run_upload_geocoding_job, args=(job_id, extracted_items))
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'job_id': job_id})
    except Exception as e:
        print(f"Error processing manual addresses: {e}")
        return jsonify({'error': f"Failed to process addresses: {str(e)}"}), 500

@app.route('/api/upload-raw-text', methods=['POST'])
def api_upload_raw_text():
    data = request.get_json() or {}
    raw_text = data.get('text', '')
    if not raw_text.strip():
        return jsonify({'error': 'No text provided'}), 400
        
    try:
        parsed = parse_pdf_text(raw_text)
        extracted_items = format_parsed_addresses(parsed)
        job_id = str(uuid.uuid4())
        JOB_STATUSES[job_id] = {'status': 'processing', 'message': 'Raw text extracted. Starting geocoding...'}
        
        thread = threading.Thread(target=run_upload_geocoding_job, args=(job_id, extracted_items))
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'job_id': job_id})
    except Exception as e:
        print(f"Error processing raw text: {e}")
        return jsonify({'error': f"Failed to process raw text: {str(e)}"}), 500"""

if old_api_upload in content:
    content = content.replace(old_api_upload, new_api_upload)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Success")
else:
    print("Could not find old api upload block!")
