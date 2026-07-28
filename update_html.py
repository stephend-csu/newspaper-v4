import sys

filepath = r"c:\Users\stardust\Desktop\newspaper-v4-main\upload.html"
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. CSS Additions
old_css = ".btn-upload:hover { background-color: #ffffff; }"
new_css = """.btn-upload:hover { background-color: #ffffff; }
    .manual-section {
      width: 100%; margin-bottom: 30px;
    }
    .manual-section h3 {
      font-size: 1.1rem; color: #eeeeee; margin-bottom: 10px; font-weight: 500;
    }
    .manual-textarea {
      width: 100%; height: 120px; background-color: #1e1e1e; border: 1px solid #444444;
      color: #cccccc; padding: 12px; border-radius: 4px; font-family: monospace;
      resize: vertical; margin-bottom: 10px;
    }
    .manual-textarea:focus { border-color: #888888; outline: none; }
    .timer { font-weight: bold; color: #ffeb3b; margin-left: 10px; }"""
content = content.replace(old_css, new_css)

# 2. Add multiple attribute
content = content.replace('<input type="file" id="fileInput" accept=".pdf">', '<input type="file" id="fileInput" accept=".pdf" multiple>')

# 3. Add manual sections HTML
old_html = """    <div class="api-section">"""
new_html = """    <div class="manual-section">
      <h3>Enter Normal Addresses Manually</h3>
      <textarea id="manualAddresses" class="manual-textarea" placeholder="e.g. 123 Main St\n456 Oak Ave\n..."></textarea>
      <button type="button" class="btn-upload" onclick="submitManualAddresses()">Process Addresses</button>
      <div class="status-msg" id="manualAddressesStatus"></div>
    </div>

    <div class="manual-section">
      <h3>Paste Raw PDF Text</h3>
      <textarea id="rawPdfText" class="manual-textarea" placeholder="Paste extracted layout text from a PDF here..."></textarea>
      <button type="button" class="btn-upload" onclick="submitRawText()">Process Raw Text</button>
      <div class="status-msg" id="rawTextStatus"></div>
    </div>

    <div class="api-section">"""
content = content.replace(old_html, new_html)

# 4. JS updates
old_js = """    function handleFile(file) {
      if (file.type !== 'application/pdf' && !file.name.endsWith('.pdf')) {
        statusMsg.style.color = '#ff6b6b';
        statusMsg.textContent = 'Error: Please upload a valid PDF file.';
        return;
      }

      statusMsg.style.color = '#ffffff';
      statusMsg.textContent = 'Extracting and geocoding addresses... This may take up to 20 seconds. Please wait...';

      const formData = new FormData();
      formData.append('pdf_file', file);

      fetch('/api/upload-pdf', {
        method: 'POST',
        body: formData
      })
      .then(res => res.json())
      .then(data => {
        if (data.error) {
          statusMsg.style.color = '#ff6b6b';
          statusMsg.textContent = 'Error: ' + data.error;
        } else if (data.job_id) {
          pollUploadJob(data.job_id);
        }
      })
      .catch(err => {
        statusMsg.style.color = '#ff6b6b';
        statusMsg.textContent = 'Failed to upload PDF: ' + err;
      });
    }"""

new_js = """    let timerInterval = null;
    let startTime = 0;

    function startTimer(statusElement) {
      if (timerInterval) clearInterval(timerInterval);
      startTime = Date.now();
      
      const updateTimer = () => {
        const seconds = Math.floor((Date.now() - startTime) / 1000);
        
        // Remove old timer if exists
        let currentText = statusElement.innerHTML;
        currentText = currentText.replace(/<span class="timer">.*?<\\/span>/, '');
        
        statusElement.innerHTML = currentText + ` <span class="timer">[Time elapsed: ${seconds}s]</span>`;
      };
      
      timerInterval = setInterval(updateTimer, 1000);
    }

    function stopTimer() {
      if (timerInterval) clearInterval(timerInterval);
      timerInterval = null;
    }

    function handleFile(file) {
      handleFiles([file]);
    }

    function handleFiles(files) {
      let hasValid = false;
      const formData = new FormData();
      
      for (let i = 0; i < files.length; i++) {
        const f = files[i];
        if (f.type === 'application/pdf' || f.name.endsWith('.pdf')) {
          formData.append('pdf_file', f);
          hasValid = true;
        }
      }

      if (!hasValid) {
        statusMsg.style.color = '#ff6b6b';
        statusMsg.textContent = 'Error: Please upload at least one valid PDF file.';
        return;
      }

      statusMsg.style.color = '#ffffff';
      statusMsg.textContent = `Uploading ${files.length} PDF(s). Extracting and geocoding addresses...`;
      startTimer(statusMsg);

      fetch('/api/upload-pdf', {
        method: 'POST',
        body: formData
      })
      .then(res => res.json())
      .then(data => {
        if (data.error) {
          stopTimer();
          statusMsg.style.color = '#ff6b6b';
          statusMsg.textContent = 'Error: ' + data.error;
        } else if (data.job_id) {
          pollUploadJob(data.job_id, statusMsg);
        }
      })
      .catch(err => {
        stopTimer();
        statusMsg.style.color = '#ff6b6b';
        statusMsg.textContent = 'Failed to upload PDF: ' + err;
      });
    }

    function submitManualAddresses() {
      const text = document.getElementById('manualAddresses').value;
      const statusEl = document.getElementById('manualAddressesStatus');
      
      if (!text.trim()) return;
      
      statusEl.style.color = '#ffffff';
      statusEl.textContent = 'Processing manual addresses...';
      startTimer(statusEl);

      fetch('/api/upload-manual-addresses', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ addresses: text })
      })
      .then(res => res.json())
      .then(data => {
        if (data.error) {
          stopTimer();
          statusEl.style.color = '#ff6b6b';
          statusEl.textContent = 'Error: ' + data.error;
        } else if (data.job_id) {
          pollUploadJob(data.job_id, statusEl);
        }
      })
      .catch(err => {
        stopTimer();
        statusEl.style.color = '#ff6b6b';
        statusEl.textContent = 'Failed: ' + err;
      });
    }

    function submitRawText() {
      const text = document.getElementById('rawPdfText').value;
      const statusEl = document.getElementById('rawTextStatus');
      
      if (!text.trim()) return;
      
      statusEl.style.color = '#ffffff';
      statusEl.textContent = 'Processing raw text...';
      startTimer(statusEl);

      fetch('/api/upload-raw-text', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text })
      })
      .then(res => res.json())
      .then(data => {
        if (data.error) {
          stopTimer();
          statusEl.style.color = '#ff6b6b';
          statusEl.textContent = 'Error: ' + data.error;
        } else if (data.job_id) {
          pollUploadJob(data.job_id, statusEl);
        }
      })
      .catch(err => {
        stopTimer();
        statusEl.style.color = '#ff6b6b';
        statusEl.textContent = 'Failed: ' + err;
      });
    }"""
content = content.replace(old_js, new_js)

old_poll = """    function pollUploadJob(jobId) {
      fetch('/api/job-status/' + jobId)
        .then(res => res.json())
        .then(data => {
          if (data.error) {
            statusMsg.style.color = '#ff6b6b';
            statusMsg.textContent = 'Error: ' + data.error;
            return;
          }
          if (data.status === 'error') {
            statusMsg.style.color = '#ff6b6b';
            statusMsg.textContent = 'Error: ' + data.message;
          } else if (data.status === 'completed') {
            statusMsg.style.color = '#51cf66';
            statusMsg.textContent = `Extracted ${data.data.total_extracted} addresses! Redirecting to Confirmation Screen...`;
            localStorage.setItem('extracted_route_data', JSON.stringify(data.data));
            setTimeout(() => {
              window.location.href = '/confirmation';
            }, 1000);
          } else {
            statusMsg.textContent = data.message || 'Extracting and geocoding addresses... This may take up to 30 seconds. Please wait...';
            setTimeout(() => pollUploadJob(jobId), 2000);
          }
        })
        .catch(err => {
          statusMsg.style.color = '#ff6b6b';
          statusMsg.textContent = 'Failed to poll status: ' + err;
        });
    }"""

new_poll = """    function pollUploadJob(jobId, statusElement) {
      fetch('/api/job-status/' + jobId)
        .then(res => res.json())
        .then(data => {
          if (data.error) {
            stopTimer();
            statusElement.style.color = '#ff6b6b';
            statusElement.textContent = 'Error: ' + data.error;
            return;
          }
          if (data.status === 'error') {
            stopTimer();
            statusElement.style.color = '#ff6b6b';
            statusElement.textContent = 'Error: ' + data.message;
          } else if (data.status === 'completed') {
            stopTimer();
            statusElement.style.color = '#51cf66';
            statusElement.textContent = `Extracted ${data.data.total_extracted} addresses! Redirecting to Confirmation Screen...`;
            localStorage.setItem('extracted_route_data', JSON.stringify(data.data));
            setTimeout(() => {
              window.location.href = '/confirmation';
            }, 1000);
          } else {
            let msg = data.message || 'Extracting and geocoding addresses... Please wait...';
            // Insert the msg into the element, but keep the timer span if it exists
            const timerHtml = statusElement.querySelector('.timer')?.outerHTML || '';
            statusElement.innerHTML = msg + ' ' + timerHtml;
            setTimeout(() => pollUploadJob(jobId, statusElement), 2000);
          }
        })
        .catch(err => {
          stopTimer();
          statusElement.style.color = '#ff6b6b';
          statusElement.textContent = 'Failed to poll status: ' + err;
        });
    }"""
content = content.replace(old_poll, new_poll)

# Fix file drag/drop support for multiple
content = content.replace('handleFile(files[0]);', 'handleFiles(files);')
content = content.replace('handleFile(e.target.files[0]);', 'handleFiles(e.target.files);')

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Success")
