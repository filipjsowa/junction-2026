document.addEventListener('DOMContentLoaded', () => {
    // Navigation
    const navLinks = document.querySelectorAll('.sidebar a');
    const pages = document.querySelectorAll('.page');

    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = link.getAttribute('data-target');
            
            navLinks.forEach(l => l.classList.remove('active'));
            link.classList.add('active');
            
            pages.forEach(p => p.classList.remove('active'));
            document.getElementById(targetId).classList.add('active');

            // Load data when tab is switched
            if (targetId === 'page-metrics') loadMetrics();
            if (targetId === 'page-review') loadReviewQueue();
        });
    });

    // Check Page
    const btnCheck = document.getElementById('btn-check');
    const textarea = document.getElementById('check-textarea');
    const resultsCard = document.getElementById('check-results');

    btnCheck.addEventListener('click', async () => {
        const text = textarea.value.trim();
        if (!text) return;

        btnCheck.disabled = true;
        btnCheck.textContent = 'Checking...';
        resultsCard.classList.add('hidden');

        try {
            const res = await fetch('/score', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text, platform: 'web' })
            });

            if (!res.ok) throw new Error('API Error');
            const data = await res.json();
            renderCheckResults(data);
        } catch (error) {
            console.error('Error fetching score:', error);
            alert('Failed to check message. Ensure API is running.');
        } finally {
            btnCheck.disabled = false;
            btnCheck.textContent = 'Check for Swarms';
        }
    });

    function renderCheckResults(data) {
        let verdictClass = 'verdict-unknown';
        if (data.score >= 0.8) verdictClass = 'verdict-danger';
        else if (data.score !== null) verdictClass = 'verdict-success';

        const isUnknown = data.score === null;
        const displayScore = isUnknown ? '--' : data.score.toFixed(2);
        const displayVerdict = data.verdict.replace(/_/g, ' ');
        
        let html = `
            <div class="results-header">
                <div>
                    <span class="verdict-badge ${verdictClass}">${displayVerdict}</span>
                </div>
                <div class="score-display">${displayScore} <span>/ 1.0</span></div>
            </div>
        `;

        if (!isUnknown && data.matched_cluster) {
            html += `
                <div style="margin-bottom: 1.5rem;">
                    <strong>Matched Cluster #${data.matched_cluster.id}</strong>
                    <div style="color: var(--text-muted); margin-top: 0.25rem;">Narrative: ${data.matched_cluster.narrative}</div>
                </div>
            `;
        }

        if (data.reasons && data.reasons.length > 0) {
            html += `<div class="reasons-container"><h3>Coordination Evidence</h3>`;
            data.reasons.forEach(r => {
                // Determine bar width based on contribution (assuming max 2.0 for styling purposes)
                const width = Math.min(100, (Math.abs(r.contribution) / 2) * 100);
                html += `
                    <div class="reason-row">
                        <div class="reason-header">
                            <strong>${r.feature.replace(/_/g, ' ')}</strong>
                            <span>+${r.contribution.toFixed(2)}</span>
                        </div>
                        <div class="bar-bg">
                            <div class="bar-fill" style="width: ${width}%"></div>
                        </div>
                        <div class="reason-text">${r.text}</div>
                    </div>
                `;
            });
            html += `</div>`;
        }

        if (data.techniques && data.techniques.length > 0) {
            html += `<div class="techniques-container"><h3>Identified Techniques</h3>`;
            data.techniques.forEach(t => {
                html += `
                    <div class="technique-item">
                        <strong>${t.name}</strong>
                        <p style="margin-top:0.5rem; font-style:italic">"${t.quote}"</p>
                    </div>
                `;
            });
            html += `</div>`;
        }

        if (data.evidence && data.evidence.length > 0) {
            html += `<div class="evidence-container"><h3>Evidence Messages</h3><ul class="evidence-list">`;
            data.evidence.forEach(e => {
                html += `
                    <li class="evidence-item">
                        <div class="evidence-meta">
                            <span>Platform: ${e.platform}</span>
                            <span>Channel: ${e.channel}</span>
                            <span>Similarity: ${e.similarity.toFixed(2)}</span>
                        </div>
                        <div>${e.text}</div>
                    </li>
                `;
            });
            html += `</ul></div>`;
        }

        resultsCard.innerHTML = html;
        resultsCard.classList.remove('hidden');
    }

    async function loadMetrics() {
        try {
            const res = await fetch('/metrics');
            if (res.ok) {
                const data = await res.json();
                document.getElementById('metric-precision').textContent = data.precision !== null ? (data.precision * 100).toFixed(1) + '%' : '--';
                document.getElementById('metric-fpr').textContent = data.false_positive_rate !== null ? (data.false_positive_rate * 100).toFixed(1) + '%' : '--';
                document.getElementById('metric-labels').textContent = data.n_labels;
            }
        } catch (e) {
            console.error('Failed to load metrics:', e);
        }
    }

    async function loadReviewQueue() {
        const container = document.getElementById('review-queue');
        try {
            const res = await fetch('/review/queue');
            if (res.ok) {
                const queue = await res.json();
                
                if (queue.length === 0) {
                    container.innerHTML = '<p class="empty-state">No clusters currently need review.</p>';
                    return;
                }
                
                let html = '';
                queue.forEach(q => {
                    // Fallbacks for fixture/mock structure
                    const score = q.auto_score !== undefined ? q.auto_score.toFixed(2) : 'N/A';
                    html += `
                        <div class="review-item">
                            <h3>Cluster #${q.id}</h3>
                            <p style="color: var(--text-muted); margin-bottom: 0.5rem;">Auto Score: ${score}</p>
                            <div class="review-actions" data-id="${q.id}">
                                <button class="btn btn-success btn-label" data-label="confirmed">Confirm Swarm</button>
                                <button class="btn btn-danger btn-label" data-label="rejected">Reject</button>
                                <button class="btn btn-warning btn-label" data-label="benign">Benign Topic</button>
                                <input type="text" placeholder="Optional reviewer note..." class="review-note">
                            </div>
                        </div>
                    `;
                });
                container.innerHTML = html;

                container.querySelectorAll('.btn-label').forEach(btn => {
                    btn.addEventListener('click', async (e) => {
                        const label = e.target.getAttribute('data-label');
                        const actionsDiv = e.target.closest('.review-actions');
                        const clusterId = actionsDiv.getAttribute('data-id');
                        const note = actionsDiv.querySelector('.review-note').value;
                        const pwd = document.getElementById('reviewer-password').value;

                        if (!pwd) {
                            alert('Please enter the shared reviewer password first.');
                            document.getElementById('reviewer-password').focus();
                            return;
                        }

                        // Disable buttons during request
                        actionsDiv.querySelectorAll('button').forEach(b => b.disabled = true);

                        try {
                            const res = await fetch(`/clusters/${clusterId}/label`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ label, by: 'reviewer', note, password: pwd })
                            });
                            
                            if (res.ok) {
                                actionsDiv.closest('.review-item').remove();
                                if (container.children.length === 0) {
                                    container.innerHTML = '<p class="empty-state">No clusters currently need review.</p>';
                                }
                            } else {
                                alert('Failed to label cluster. Check password and try again.');
                                actionsDiv.querySelectorAll('button').forEach(b => b.disabled = false);
                            }
                        } catch (err) {
                            console.error(err);
                            alert('Network error while labeling cluster.');
                            actionsDiv.querySelectorAll('button').forEach(b => b.disabled = false);
                        }
                    });
                });
            } else {
                 container.innerHTML = '<p class="empty-state">Failed to load queue. API may not be running.</p>';
            }
        } catch (e) {
            console.error('Failed to load review queue:', e);
            container.innerHTML = '<p class="empty-state">Failed to load queue. API may not be running.</p>';
        }
    }
});
