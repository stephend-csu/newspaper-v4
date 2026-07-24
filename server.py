import os
import uuid
import threading
from flask import Flask, request, jsonify, send_from_directory, render_template

from pdf_extractor import extract_addresses_from_pdf_stream
from geocoder import validate_and_classify_addresses, suggest_addresses
from router import optimize_road_route, generate_chapters_csv
from github_sync import sync_chapters_and_metadata_to_github

app = Flask(__name__, template_folder='templates', static_folder='.')

# Background jobs registry
JOB_STATUSES = {}

@app.route('/')
@app.route('/upload')
@app.route('/upload.html')
def upload_page():
    return send_from_directory('.', 'upload.html')

@app.route('/confirmation')
@app.route('/confirm')
@app.route('/confirm.html')
def confirm_page():
    return send_from_directory('.', 'confirm.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('.', filename)

def run_upload_geocoding_job(job_id, extracted_items):
    try:
        JOB_STATUSES[job_id] = {'status': 'processing', 'message': 'Validating and geocoding addresses via ArcGIS...'}
        valid_list, problem_list = validate_and_classify_addresses(extracted_items)
        
        newspaper_counts = {}
        for item in extracted_items:
            for paper in item.get('newspapers', []):
                newspaper_counts[paper] = newspaper_counts.get(paper, 0) + 1
                
        JOB_STATUSES[job_id] = {
            'status': 'completed',
            'data': {
                'success': True,
                'newspaper_counts': newspaper_counts,
                'valid_addresses': valid_list,
                'problem_addresses': problem_list,
                'total_extracted': len(extracted_items)
            }
        }
    except Exception as e:
        print(f"Job {job_id} geocoding error: {e}")
        JOB_STATUSES[job_id] = {'status': 'error', 'message': f'Geocoding failed: {str(e)}'}

@app.route('/api/upload-pdf', methods=['POST'])
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
        return jsonify({'error': f"Failed to process PDF: {str(e)}"}), 500

@app.route('/api/geocode-suggest', methods=['GET'])
def api_geocode_suggest():
    query = request.args.get('q', '').strip()
    suggestions = suggest_addresses(query)
    return jsonify({'suggestions': suggestions})

def run_route_processing_job(job_id, confirmed_addresses, unconfirmed_count, newspaper_counts, not_routed_addresses=None):
    try:
        JOB_STATUSES[job_id] = {'status': 'processing', 'message': 'Optimizing road route...'}
        
        # 1. Optimize route using OSRM
        route_waypoints = optimize_road_route(confirmed_addresses)
        
        JOB_STATUSES[job_id]['message'] = 'Generating Chapters.csv...'
        
        # 2. Generate Chapters.csv content
        csv_content = generate_chapters_csv(route_waypoints)
        
        JOB_STATUSES[job_id]['message'] = 'Uploading to GitHub...'
        
        # 3. Build metadata
        metadata = {
            'addresses_found': len(confirmed_addresses),
            'addresses_not_found': unconfirmed_count,
            'newspaper_counts': newspaper_counts,
            'total_stops': len(route_waypoints),
            'not_routed_addresses': not_routed_addresses or []
        }
        
        # 4. Sync with GitHub
        success = sync_chapters_and_metadata_to_github(csv_content, metadata)
        
        if success:
            JOB_STATUSES[job_id] = {
                'status': 'completed',
                'message': 'Successfully processed route and updated GitHub!',
                'metadata': metadata
            }
        else:
            JOB_STATUSES[job_id] = {
                'status': 'error',
                'message': 'Saved files locally, but GitHub upload encountered an issue.'
            }
    except Exception as e:
        print(f"Job {job_id} error: {e}")
        JOB_STATUSES[job_id] = {
            'status': 'error',
            'message': f"Processing error: {str(e)}"
        }

@app.route('/api/process-route', methods=['POST'])
def api_process_route():
    data = request.get_json() or {}
    confirmed = data.get('confirmed_valid_addresses', [])
    unconfirmed_count = data.get('unconfirmed_count', 0)
    newspaper_counts = data.get('newspaper_counts', {})
    not_routed = data.get('not_routed_addresses', [])
    
    if not confirmed:
        return jsonify({'error': 'No valid addresses provided for routing'}), 400
        
    job_id = str(uuid.uuid4())
    JOB_STATUSES[job_id] = {'status': 'processing', 'message': 'Job started...'}
    
    thread = threading.Thread(
        target=run_route_processing_job,
        args=(job_id, confirmed, unconfirmed_count, newspaper_counts, not_routed)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'job_id': job_id,
        'status': 'processing',
        'message': 'Route calculation started in background. Polling job status.'
    })

@app.route('/api/job-status/<job_id>', methods=['GET'])
def api_job_status(job_id):
    job_info = JOB_STATUSES.get(job_id)
    if not job_info:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(job_info)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=True)
