import os
import json
import base64
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

def get_pst_timestamp():
    """
    Returns current date & time string in Pacific Standard/Daylight Time (PST/PDT).
    """
    pst = ZoneInfo('America/Los_Angeles')
    now = datetime.now(pst)
    return now.strftime('%b %d, %Y %I:%M %p PST')

def update_file_in_github(file_path_in_repo, file_content_str, commit_message):
    """
    Commits/updates a file directly in GitHub repository via REST API.
    Returns boolean indicating success.
    """
    token = os.getenv('GITHUB_TOKEN') or os.getenv('GH_TOKEN')
    repo = os.getenv('GITHUB_REPO', 'stephend-csu/newspaper-v4')
    
    if not token:
        print("GITHUB_TOKEN not found in environment. Saving file locally.")
        try:
            local_path = os.path.join(os.path.dirname(__file__), file_path_in_repo)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, 'w', encoding='utf-8') as f:
                f.write(file_content_str)
            print(f"Successfully saved to local path: {local_path}")
            return True
        except Exception as e:
            print(f"Error saving file locally: {e}")
            return False
            
    url = f"https://api.github.com/repos/{repo}/contents/{file_path_in_repo}"
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    try:
        # Check if file exists to obtain current SHA
        sha = None
        get_resp = requests.get(url, headers=headers, timeout=10)
        if get_resp.status_code == 200:
            sha = get_resp.json().get('sha')
            
        encoded_content = base64.b64encode(file_content_str.encode('utf-8')).decode('utf-8')
        
        payload = {
            'message': commit_message,
            'content': encoded_content,
            'branch': 'main'
        }
        if sha:
            payload['sha'] = sha
            
        put_resp = requests.put(url, headers=headers, json=payload, timeout=10)
        if put_resp.status_code in [200, 201]:
            print(f"Successfully committed {file_path_in_repo} to GitHub repository {repo}")
            return True
        else:
            print(f"GitHub API commit error ({put_resp.status_code}): {put_resp.text}")
            # Fallback to local write
            local_path = os.path.join(os.path.dirname(__file__), file_path_in_repo)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, 'w', encoding='utf-8') as f:
                f.write(file_content_str)
            return True
    except Exception as e:
        print(f"Failed to commit {file_path_in_repo} to GitHub: {e}")
        # Save locally
        try:
            local_path = os.path.join(os.path.dirname(__file__), file_path_in_repo)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, 'w', encoding='utf-8') as f:
                f.write(file_content_str)
            return True
        except Exception as le:
            print(f"Failed local fallback save: {le}")
            return False

def sync_chapters_and_metadata_to_github(csv_content_str, metadata_dict):
    """
    Saves/commits both Chapters.csv and metadata.json to GitHub.
    """
    pst_time = get_pst_timestamp()
    metadata_dict['upload_timestamp_pst'] = pst_time
    
    metadata_json_str = json.dumps(metadata_dict, indent=2)
    
    # Save/commit Chapters.csv
    csv_ok = update_file_in_github('csv/Chapters.csv', csv_content_str, f"Update Chapters.csv route data - {pst_time}")
    
    # Save/commit metadata.json
    meta_ok = update_file_in_github('csv/metadata.json', metadata_json_str, f"Update metadata.json - {pst_time}")
    
    return csv_ok and meta_ok
