import { useState, useMemo } from 'react';
import { rnd } from '../data/mockData.js';

const PIPELINE_NODES = [
  { id: 'received', label: 'Receive Email' },
  { id: 'whitelist', label: 'Whitelist Verify' },
  { id: 'cleaned', label: 'Clean Email' },
  { id: 'classified', label: 'AI Classification' },
  { id: 'ner', label: 'Entity Extraction' },
  { id: 'validation', label: 'Business Validation' },
  { id: 'api', label: 'SNOC API Call' },
  { id: 'reply', label: 'Email Response' },
  { id: 'completed', label: 'Audit Log' }
];

export default function DecisionDrawer({ request, onClose }) {
  const [tab, setTab] = useState('email');

  const pipelineTimes = useMemo(() => ({
    received: rnd(8, 20) + ' ms',
    whitelist: rnd(2, 8) + ' ms',
    cleaned: rnd(10, 25) + ' ms',
    classified: rnd(320, 520) + ' ms',
    ner: rnd(80, 160) + ' ms',
    validation: rnd(15, 40) + ' ms',
    api: request && request.status === 'Success' ? rnd(450, 950) + ' ms' : '—',
    reply: request && request.status === 'Success' ? rnd(150, 320) + ' ms' : '—'
  }), [request]);

  if (!request) return <aside className="detail-drawer" id="detail-drawer"></aside>;

  let activeCount;
  if (request.status === 'Success') activeCount = 9;
  else if (request.status === 'Escalated') activeCount = request.reasons.some(r => r.includes('whitelist')) ? 2 : 6;
  else if (request.status === 'Processing') activeCount = 6;
  else activeCount = 3;

  const decisionRoute = request.status === 'Success' ? 'AUTOMATIC RESPONSE'
    : request.status === 'Escalated' ? 'ESCALATED TO SUPERVISOR'
    : request.status === 'Processing' ? 'IN PROGRESS' : 'DROPPED — NO ACTION';

  return (
    <aside className="detail-drawer open" id="detail-drawer">
      <div className="drawer-header">
        <div className="drawer-title">
          <h3>AI Decision Inspector</h3>
          <span className="drawer-subtitle">Request ID: #{request.id}</span>
        </div>
        <button className="close-drawer-btn" title="Close Drawer" onClick={onClose}>
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>

      <div className="drawer-body">
        <div className="drawer-section">
          <h4>Execution Pipeline Lifecycle</h4>
          <div className="pipeline-flow-wrapper">
            {PIPELINE_NODES.map((node, i) => (
              <div className={`pipe-node${i < activeCount ? ' active-node' : ''}`} key={node.id}>
                <div className="node-icon">✔</div>
                <div className="node-meta">
                  <span className="lbl">{node.label}</span>
                  <span className="time">{node.id === 'completed' ? (activeCount === 9 ? 'Completed' : '—') : pipelineTimes[node.id]}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="drawer-divider"></div>

        <div className="drawer-section">
          <h4>Decision Rationale</h4>
          <div className="decision-meta-row">
            <div className="lbl-val-box"><span className="lbl">Confidence Score</span><span className={`val ${request.confidence >= 85 ? 'text-success' : 'highlight-red'}`}>{request.confidence}%</span></div>
            <div className="lbl-val-box"><span className="lbl">System Threshold</span><span className="val">85%</span></div>
            <div className="lbl-val-box"><span className="lbl">Route Decision</span><span className="val badge badge-success">{decisionRoute}</span></div>
          </div>
          <div className="confidence-reasons-box">
            <h5>Confidence Breakdown & Rules Matched</h5>
            <ul className="reasons-list">
              {request.reasons.map((r, i) => <li key={i}>{r}</li>)}
            </ul>
          </div>
        </div>

        <div className="drawer-divider"></div>

        <div className="drawer-section">
          <h4>Payload Details</h4>
          <div className="payload-tab-container">
            <div className="payload-tab-header">
              <button className={`payload-tab-btn${tab === 'email' ? ' active' : ''}`} onClick={() => setTab('email')}>Email Text</button>
              <button className={`payload-tab-btn${tab === 'extracted' ? ' active' : ''}`} onClick={() => setTab('extracted')}>Extracted Values</button>
              <button className={`payload-tab-btn${tab === 'api' ? ' active' : ''}`} onClick={() => setTab('api')}>API Exchange</button>
            </div>

            {tab === 'email' && (
              <div className="payload-tab-content active">
                <div className="email-viewer-header">
                  <div><strong>From:</strong> <span>{request.sender}</span></div>
                  <div><strong>Subject:</strong> <span>{request.intent}{request.pdv ? ` PDV ${request.pdv}` : ''}</span></div>
                  <div><strong>Date:</strong> <span>{request.dateFull}</span></div>
                </div>
                <div className="email-viewer-body">{request.emailBody.split('\n').map((line, i) => <span key={i}>{line}<br/></span>)}</div>
                <div className="email-viewer-cleaned-header">Cleaned Email Text (AI Input)</div>
                <div className="email-viewer-body cleaned-body">{request.cleanedBody}</div>
              </div>
            )}

            {tab === 'extracted' && (
              <div className="payload-tab-content active">
                <div className="extracted-panel">
                  <div className="extracted-row"><span className="label">Detected Intent</span><span className="value code-val">{request.intent}</span></div>
                  <div className="extracted-row"><span className="label">Extracted PDV Code</span><span className="value code-val">{request.pdv || 'None'}</span></div>
                  <div className="extracted-row"><span className="label">Extracted OTP Key</span><span className="value code-val">{request.typeKey === 'OTP' ? 'Parsed from request' : 'None'}</span></div>
                  <div className="extracted-row"><span className="label">Extracted MSISDN</span><span className="value code-val">{request.phone || 'None'}</span></div>
                  <div className="extracted-row"><span className="label">Dialect Language</span><span className="value code-val">{request.lang}</span></div>
                </div>
              </div>
            )}

            {tab === 'api' && (
              <div className="payload-tab-content active">
                <div className="api-viewer-box">
                  <div className="api-viewer-title">Request Body {request.apiRequest ? `(POST ${request.apiRequest.endpoint})` : ''}</div>
                  <pre className="api-pre">{request.apiRequest ? JSON.stringify(request.apiRequest, null, 2) : '// No API call executed for this request'}</pre>
                  <div className="api-viewer-title">Response Payload</div>
                  <pre className="api-pre">{request.apiResponse ? JSON.stringify(request.apiResponse, null, 2) : '// No response payload'}</pre>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="drawer-divider"></div>

        <div className="drawer-section">
          <h4>Outgoing Response Preview</h4>
          <div className="email-viewer-header">
            <div><strong>To:</strong> <span>{request.sender}</span></div>
            <div><strong>Subject:</strong> <span>{request.replySubj || 'No reply sent'}</span></div>
          </div>
          <div className="email-viewer-body reply-body">
            {request.replyBody
              ? request.replyBody.split('\n').map((line, i) => <span key={i}>{line}<br/></span>)
              : <span style={{ color: '#94A3B8' }}>No outgoing reply was generated for this request.</span>}
          </div>
        </div>
      </div>
    </aside>
  );
}
