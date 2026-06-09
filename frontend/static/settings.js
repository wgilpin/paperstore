/* PaperStore — settings page script */

(function() {
  const aboutMeInput = document.getElementById('about-me');
  const saveBtn = document.getElementById('save-btn');
  const statusMsg = document.getElementById('status-msg');

  if (!aboutMeInput || !saveBtn || !statusMsg) return;

  // Load current settings
  async function loadSettings() {
    saveBtn.disabled = true;
    statusMsg.className = '';
    statusMsg.textContent = 'Loading settings...';
    try {
      const res = await fetch(`${API}/api/settings`);
      if (res.ok) {
        const data = await res.json();
        aboutMeInput.value = data.about_me || '';
        statusMsg.textContent = '';
      } else {
        statusMsg.className = 'error';
        statusMsg.textContent = 'Failed to load settings.';
      }
    } catch {
      statusMsg.className = 'error';
      statusMsg.textContent = 'Network error — is the server running?';
    } finally {
      saveBtn.disabled = false;
    }
  }

  // Save settings
  async function saveSettings() {
    saveBtn.disabled = true;
    statusMsg.className = '';
    statusMsg.textContent = 'Saving settings...';
    const about_me = aboutMeInput.value.trim();

    try {
      const res = await fetch(`${API}/api/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ about_me }),
      });
      if (res.ok) {
        const data = await res.json();
        aboutMeInput.value = data.about_me || '';
        statusMsg.className = 'success';
        statusMsg.textContent = 'Settings saved successfully!';
        setTimeout(() => {
          if (statusMsg.className === 'success') {
            statusMsg.textContent = '';
          }
        }, 3000);
      } else {
        statusMsg.className = 'error';
        statusMsg.textContent = 'Failed to save settings.';
      }
    } catch {
      statusMsg.className = 'error';
      statusMsg.textContent = 'Network error — is the server running?';
    } finally {
      saveBtn.disabled = false;
    }
  }

  saveBtn.addEventListener('click', saveSettings);
  loadSettings();
})();
