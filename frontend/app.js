const API_BASE = 'http://peakalert-alb-851566986.us-east-1.elb.amazonaws.com';

let allAlerts = [];

async function loadAlerts() {
    const container = document.getElementById('alerts-container');
    try {
        const response = await fetch(`${API_BASE}/api/alerts`);
        const data = await response.json();
        allAlerts = data.alerts || [];
        document.getElementById('total-alerts').textContent = data.count || 0;
        document.getElementById('server-instance').textContent = (data.instance || 'unknown').substring(0, 12);
        document.getElementById('footer-instance').textContent = `Served by: ${data.instance || 'unknown'}`;
        const severeCount = allAlerts.filter(a => a.severity === 'severe' || a.severity === 'extreme').length;
        document.getElementById('severe-count').textContent = severeCount;
        document.getElementById('last-updated').textContent = `Last updated: ${new Date().toLocaleTimeString()}`;
        renderAlerts(allAlerts);
    } catch (error) {
        container.innerHTML = `<div class="no-alerts"><h3>⚠️ Unable to load alerts</h3><p>Error: ${error.message}</p></div>`;
    }
}

function renderAlerts(alerts) {
    const container = document.getElementById('alerts-container');
    if (!alerts || alerts.length === 0) {
        container.innerHTML = `<div class="no-alerts"><h3>✅ No Active Alerts</h3><p>All monitored trails are clear!</p></div>`;
        return;
    }
    container.innerHTML = alerts.map(alert => `
        <div class="alert-card severity-${alert.severity || 'info'}">
            <div class="alert-trail">📍 ${escapeHtml(alert.trail_name)}</div>
            <div class="alert-message">${escapeHtml(alert.alert_message)}</div>
            <div class="alert-meta">
                <span class="severity-badge ${alert.severity || 'info'}">${getSeverityIcon(alert.severity)} ${alert.severity || 'info'}</span>
                <span class="alert-time">🕐 ${formatTime(alert.timestamp)}</span>
            </div>
            ${alert.expires ? `<div class="alert-time" style="margin-top:0.5rem">Expires: ${formatTime(alert.expires)}</div>` : ''}
        </div>
    `).join('');
}

async function loadTrails() {
    try {
        const response = await fetch(`${API_BASE}/api/trails`);
        const data = await response.json();
        document.getElementById('trails-count').textContent = (data.trails || []).length;
    } catch (error) {
        document.getElementById('trails-count').textContent = '--';
    }
}

async function loadTrends() {
    const container = document.getElementById('trend-chart');
    try {
        const response = await fetch(`${API_BASE}/api/stats`);
        const data = await response.json();
        const byDay = data.by_day || [];
        if (byDay.length === 0) {
            container.innerHTML = '<p style="text-align:center;color:#888;">No trend data yet</p>';
            return;
        }
        const maxCount = Math.max(...byDay.map(d => d.count), 1);
        container.innerHTML = `
            <div class="trend-bar-container">
                ${byDay.map(day => `
                    <div class="trend-bar-wrapper">
                        <div class="trend-bar-value">${day.count}</div>
                        <div class="trend-bar" style="height:${(day.count/maxCount)*160}px"></div>
                        <div class="trend-bar-label">${formatDate(day.date)}</div>
                    </div>
                `).join('')}
            </div>`;
    } catch (error) {
        container.innerHTML = '<p style="text-align:center;color:#888;">Unable to load trends</p>';
    }
}

function filterAlerts() {
    const query = document.getElementById('search-input').value.toLowerCase();
    if (!query) { renderAlerts(allAlerts); return; }
    const filtered = allAlerts.filter(a =>
        a.trail_name.toLowerCase().includes(query) ||
        a.alert_message.toLowerCase().includes(query) ||
        (a.severity && a.severity.toLowerCase().includes(query))
    );
    renderAlerts(filtered);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getSeverityIcon(severity) {
    return {'extreme':'🔴','severe':'🟠','moderate':'🟡','minor':'🟢','info':'🔵'}[severity] || '⚪';
}

function formatTime(timestamp) {
    if (!timestamp) return 'Unknown';
    try { return new Date(timestamp).toLocaleString(); } catch { return timestamp; }
}

function formatDate(dateStr) {
    if (!dateStr) return '';
    try { return new Date(dateStr).toLocaleDateString('en-US', {month:'short', day:'numeric'}); } catch { return dateStr; }
}

document.addEventListener('DOMContentLoaded', () => {
    loadAlerts();
    loadTrails();
    loadTrends();
    setInterval(() => { loadAlerts(); loadTrails(); loadTrends(); }, 120000);
});