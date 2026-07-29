import os
import json
import requests
import datetime
import re
from datetime import timezone, timedelta

def get_pst_timestamp():
    # Helper to get PST time string
    pst = timezone(timedelta(hours=-8))
    return datetime.datetime.now(pst).strftime('%Y-%m-%d %I:%M:%S %p PST')

def sync_chapters_and_metadata_to_github(csv_content_str, metadata_dict, run_id='default'):
    """
    Saves both Chapters.csv and metadata.json locally, and commits BOTH files
    together in a SINGLE combined GitHub commit to prevent Pages build cancellations.
    """
    pst_time = get_pst_timestamp()
    metadata_dict['upload_timestamp_pst'] = pst_time
    metadata_json_str = json.dumps(metadata_dict, indent=2)
    
    csv_filename = 'Chapters.csv' if run_id == 'default' else f'Chapters_{run_id}.csv'
    meta_filename = 'metadata.json' if run_id == 'default' else f'metadata_{run_id}.json'
    
    # 1. Always write to local disk first for immediate local availability
    try:
        csv_local = os.path.join(os.path.dirname(__file__), 'csv', csv_filename)
        meta_local = os.path.join(os.path.dirname(__file__), 'csv', meta_filename)
        os.makedirs(os.path.dirname(csv_local), exist_ok=True)
        
        with open(csv_local, 'w', encoding='utf-8', newline='') as f:
            f.write(csv_content_str)
        with open(meta_local, 'w', encoding='utf-8', newline='') as f:
            f.write(metadata_json_str)
        print(f"Successfully saved route files locally at {pst_time}")
    except Exception as e:
        print(f"Error saving files locally: {e}")

    token = os.getenv('GITHUB_TOKEN') or os.getenv('GH_TOKEN')
    repo = os.getenv('GITHUB_REPO', 'stephend-csu/newspaper-v4')
    
    if not token:
        print("GITHUB_TOKEN not found in environment. Local save complete.")
        return True

    # 2. Single Combined Commit via GitHub Git Trees API
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    commit_msg = f"Update delivery route data and metadata [{run_id}] - {pst_time}"
    
    try:
        # Step A: Get latest commit SHA on main branch
        ref_url = f"https://api.github.com/repos/{repo}/git/ref/heads/main"
        ref_resp = requests.get(ref_url, headers=headers, timeout=6)
        if ref_resp.status_code != 200:
            print(f"GitHub ref lookup notice ({ref_resp.status_code}): {ref_resp.text}")
            return True
        latest_commit_sha = ref_resp.json()['object']['sha']

        # Step B: Get tree SHA for latest commit
        commit_url = f"https://api.github.com/repos/{repo}/git/commits/{latest_commit_sha}"
        commit_resp = requests.get(commit_url, headers=headers, timeout=6)
        if commit_resp.status_code != 200:
            print(f"GitHub commit lookup notice ({commit_resp.status_code}): {commit_resp.text}")
            return True
        base_tree_sha = commit_resp.json()['tree']['sha']

        # Step C: Parse existing csv directory to find files older than 48 hours
        tree_items = [
            {
                'path': f'csv/{csv_filename}',
                'mode': '100644',
                'type': 'blob',
                'content': csv_content_str
            },
            {
                'path': f'csv/{meta_filename}',
                'mode': '100644',
                'type': 'blob',
                'content': metadata_json_str
            }
        ]
        
        # Cleanup old files
        csv_contents_url = f"https://api.github.com/repos/{repo}/contents/csv?ref=main"
        csv_resp = requests.get(csv_contents_url, headers=headers, timeout=6)
        if csv_resp.status_code == 200:
            now = datetime.datetime.utcnow()
            for item in csv_resp.json():
                if item['type'] == 'file':
                    fname = item['name']
                    # Don't delete the test files
                    if 'test' in fname:
                        continue
                        
                    # Extract timestamp YYYYMMDD-HHMMSS
                    match = re.search(r'-(\d{8}-\d{6})\.(csv|json)$', fname)
                    if match:
                        ts_str = match.group(1)
                        try:
                            file_time = datetime.datetime.strptime(ts_str, "%Y%m%d-%H%M%S")
                            age_hours = (now - file_time).total_seconds() / 3600.0
                            if age_hours > 48:
                                # Mark for deletion
                                tree_items.append({
                                    'path': f"csv/{fname}",
                                    'mode': '100644',
                                    'type': 'blob',
                                    'sha': None
                                })
                        except ValueError:
                            pass

        # Step D: Create new tree containing BOTH files and deletions
        tree_url = f"https://api.github.com/repos/{repo}/git/trees"
        tree_payload = {
            'base_tree': base_tree_sha,
            'tree': tree_items
        }
        tree_resp = requests.post(tree_url, headers=headers, json=tree_payload, timeout=8)
        if tree_resp.status_code != 201:
            print(f"GitHub tree creation notice ({tree_resp.status_code}): {tree_resp.text}")
            return True
        new_tree_sha = tree_resp.json()['sha']

        # Step E: Create single commit object
        new_commit_url = f"https://api.github.com/repos/{repo}/git/commits"
        new_commit_payload = {
            'message': commit_msg,
            'tree': new_tree_sha,
            'parents': [latest_commit_sha]
        }
        new_commit_resp = requests.post(new_commit_url, headers=headers, json=new_commit_payload, timeout=8)
        if new_commit_resp.status_code != 201:
            print(f"GitHub commit creation notice ({new_commit_resp.status_code}): {new_commit_resp.text}")
            return True
        new_commit_sha = new_commit_resp.json()['sha']

        # Step F: Update main branch reference
        update_ref_url = f"https://api.github.com/repos/{repo}/git/refs/heads/main"
        update_ref_payload = {'sha': new_commit_sha, 'force': False}
        update_ref_resp = requests.patch(update_ref_url, headers=headers, json=update_ref_payload, timeout=8)

        if update_ref_resp.status_code == 200:
            print(f"Successfully committed BOTH Chapters.csv and metadata.json in single commit: {new_commit_sha[:7]}")
            return True
        else:
            print(f"GitHub ref patch notice ({update_ref_resp.status_code}): {update_ref_resp.text}")
            return True

    except Exception as e:
        print(f"GitHub push failed: {e}")
        return False
