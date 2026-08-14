// Widget styles — injected into shadow root, zero CSS leakage in or out.
// :host resets all inherited properties from the host page.

export const STYLES = /* css */ `
:host {
  all: initial;
  font-family: var(--cw-font, 'Poppins'), sans-serif;
  font-size: 14px;
  color: #1f2937;
  box-sizing: border-box;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

/* ── CSS tokens ──────────────────────────────────────────────────────────── */
:host {
  --cp:   var(--cw-primary,   #00D9FF);
  --cs:   var(--cw-secondary, #4D27D2);
  --cbg:  var(--cw-surface,   #ffffff);
  --ct:   var(--cw-text,      #1f2937);
  --ctl:  var(--cw-text-light,#6b7280);
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
  --ease-out:    cubic-bezier(0.4, 0, 0.2, 1);
}

/* ══════════════════════════════════════
   LAUNCHER
══════════════════════════════════════ */
.launcher {
  position: fixed;
  bottom: 24px;
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--cp) 0%, var(--cs) 100%);
  color: white;
  border: none;
  cursor: pointer;
  z-index: 2147483647;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 6px 24px rgba(0,0,0,0.22);
  transition: transform 0.3s var(--ease-spring), box-shadow 0.25s var(--ease-out);
}
.launcher::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: inherit;
  opacity: 0.45;
  animation: cwPulse 2.4s ease-out infinite;
}
@keyframes cwPulse {
  0%   { transform: scale(1);   opacity: 0.45; }
  70%  { transform: scale(1.7); opacity: 0;    }
  100% { transform: scale(1.7); opacity: 0;    }
}
.launcher:hover {
  transform: scale(1.1);
  box-shadow: 0 10px 32px rgba(0,0,0,0.28);
}
.launcher.pos-right { right: 24px; }
.launcher.pos-left  { left:  24px; }
.launcher svg { width: 26px; height: 26px; position: relative; }

/* ══════════════════════════════════════
   CHAT WINDOW
══════════════════════════════════════ */
.chat-window {
  position: fixed;
  bottom: 100px;
  z-index: 2147483646;
  width: 360px;
  height: 540px;
  background: var(--cbg);
  border-radius: 20px;
  box-shadow:
    0 24px 64px rgba(0,0,0,0.14),
    0 6px 20px rgba(0,0,0,0.08),
    0 0 0 1px rgba(0,0,0,0.05);
  overflow: hidden;
  display: none;
  flex-direction: column;
  opacity: 0;
  transform: translateY(20px) scale(0.94);
  transition: opacity 0.28s var(--ease-out), transform 0.32s var(--ease-spring);
}
.chat-window.pos-right { right: 24px; }
.chat-window.pos-left  { left:  24px; }
.chat-window.open {
  display: flex;
  opacity: 1;
  transform: translateY(0) scale(1);
}

/* ══════════════════════════════════════
   HEADER
══════════════════════════════════════ */
.header {
  padding: 14px 16px;
  display: flex;
  align-items: center;
  gap: 11px;
  background: linear-gradient(135deg, var(--cs) 0%, var(--cp) 100%);
  flex-shrink: 0;
  position: relative;
}
.header::after {
  content: '';
  position: absolute;
  inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.04'/%3E%3C/svg%3E");
  pointer-events: none;
}
.header-avatar {
  width: 38px; height: 38px;
  border-radius: 50%;
  background: rgba(255,255,255,0.18);
  border: 1.5px solid rgba(255,255,255,0.3);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; position: relative; overflow: hidden;
}
.header-avatar img {
  width: 100%; height: 100%;
  object-fit: contain; border-radius: 50%;
}
.header-info { flex: 1; position: relative; }
.header-title { font-size: 14px; font-weight: 600; color: #fff; display: block; line-height: 1.2; }
.header-status { display: flex; align-items: center; gap: 5px; margin-top: 3px; }
.status-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: #4ade80; box-shadow: 0 0 0 2px rgba(74,222,128,0.3);
  animation: cwStatusPulse 2s ease-in-out infinite;
}
@keyframes cwStatusPulse {
  0%,100% { box-shadow: 0 0 0 2px rgba(74,222,128,0.3); }
  50%      { box-shadow: 0 0 0 4px rgba(74,222,128,0.15); }
}
.header-status span { font-size: 11px; color: rgba(255,255,255,0.75); }
.close-btn {
  position: relative;
  background: rgba(255,255,255,0.16);
  border: 1.5px solid rgba(255,255,255,0.25);
  color: white; cursor: pointer; border-radius: 50%;
  width: 30px; height: 30px;
  display: flex; align-items: center; justify-content: center;
  transition: background 0.2s ease, transform 0.2s ease;
  font-size: 18px; flex-shrink: 0; line-height: 1;
}
.close-btn:hover { background: rgba(255,255,255,0.28); transform: rotate(90deg) scale(1.05); }
.reset-btn {
  position: relative;
  background: rgba(255,255,255,0.16);
  border: 1.5px solid rgba(255,255,255,0.25);
  color: white; cursor: pointer; border-radius: 50%;
  width: 30px; height: 30px; margin-right: 8px;
  display: flex; align-items: center; justify-content: center;
  transition: background 0.2s ease, transform 0.2s ease;
  flex-shrink: 0; line-height: 1;
}
.reset-btn:hover { background: rgba(255,255,255,0.28); transform: rotate(-30deg) scale(1.05); }

/* ══════════════════════════════════════
   WELCOME SCREEN
══════════════════════════════════════ */
.welcome {
  flex: 1;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  padding: 36px 28px 28px;
  text-align: center;
  background: var(--cbg);
}
.welcome-icon {
  width: 68px; height: 68px; border-radius: 50%;
  background: linear-gradient(135deg, rgba(0,217,255,0.12) 0%, rgba(77,39,210,0.08) 100%);
  border: 2px solid rgba(0,217,255,0.2);
  display: flex; align-items: center; justify-content: center;
  margin-bottom: 20px;
}
.welcome-icon svg { width: 28px; height: 28px; stroke: var(--cp); }
.welcome-title { font-size: 19px; font-weight: 700; color: var(--ct); margin-bottom: 8px; line-height: 1.3; }
.welcome-sub { font-size: 13px; color: var(--ctl); line-height: 1.6; margin-bottom: 28px; max-width: 260px; }

/* Language picker */
.lang-picker {
  display: inline-flex; background: #f0f1f3;
  border-radius: 999px; padding: 3px; gap: 2px;
}
.lang-btn {
  padding: 7px 18px; background: transparent; border: none;
  border-radius: 999px; cursor: pointer; font-size: 12px; font-weight: 600;
  font-family: inherit; color: var(--ctl); letter-spacing: 0.5px;
  transition: color 0.18s ease, background 0.18s ease;
}
.lang-btn:hover { color: var(--ct); }
.lang-btn.selected { background: #fff; color: var(--ct); box-shadow: 0 1px 4px rgba(0,0,0,0.12); }

/* ══════════════════════════════════════
   CHAT BODY
══════════════════════════════════════ */
.chat-body { display: none; flex-direction: column; flex: 1; overflow: hidden; }
.chat-body.active { display: flex; }

.messages {
  flex: 1; overflow-y: auto;
  padding: 18px 14px;
  background: #f5f6f8;
  display: flex; flex-direction: column;
  gap: 8px; scroll-behavior: smooth;
}
.messages::-webkit-scrollbar { width: 4px; }
.messages::-webkit-scrollbar-track { background: transparent; }
.messages::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.12); border-radius: 4px; }

/* Bubbles */
.bubble {
  padding: 10px 14px;
  max-width: 82%;
  word-wrap: break-word;
  font-size: 13.5px;
  line-height: 1.55;
  white-space: pre-line;
  animation: cwBubbleIn 0.22s var(--ease-out);
}
@keyframes cwBubbleIn {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}
.bubble.user {
  background: linear-gradient(135deg, var(--cp) 0%, var(--cs) 100%);
  color: white; align-self: flex-end;
  border-radius: 18px 18px 4px 18px;
  box-shadow: 0 3px 10px rgba(0,0,0,0.14);
}
.bubble.bot {
  background: #ffffff; color: var(--ct); align-self: flex-start;
  border-radius: 18px 18px 18px 4px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.07);
  border: 1px solid rgba(0,0,0,0.06);
}
.bubble.optimistic { opacity: 0.65; }

/* Streaming cursor — blinks at the end of the in-progress answer bubble */
.streaming-cursor {
  display: inline-block;
  width: 2px;
  height: 1em;
  background: var(--cp);
  border-radius: 1px;
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: cwCaret 0.9s step-end infinite;
}
@keyframes cwCaret {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0; }
}

/* Typing indicator */
.typing-indicator {
  display: flex; align-items: center; gap: 5px;
  padding: 12px 15px; background: #ffffff;
  border-radius: 18px 18px 18px 4px;
  max-width: 68px; align-self: flex-start;
  box-shadow: 0 2px 8px rgba(0,0,0,0.07);
  border: 1px solid rgba(0,0,0,0.06);
  animation: cwBubbleIn 0.22s var(--ease-out);
}
.typing-dot {
  width: 7px; height: 7px; background: var(--cp);
  border-radius: 50%; opacity: 0.6;
  animation: cwTyping 1.3s ease-in-out infinite;
}
.typing-dot:nth-child(1) { animation-delay: 0s; }
.typing-dot:nth-child(2) { animation-delay: 0.18s; }
.typing-dot:nth-child(3) { animation-delay: 0.36s; }
@keyframes cwTyping {
  0%,60%,100% { transform: translateY(0); opacity: 0.5; }
  30%          { transform: translateY(-5px); opacity: 1; }
}

/* Suggested questions */
.suggestions { display: flex; flex-direction: column; gap: 6px; margin: 4px 0; align-self: flex-start; max-width: 88%; }
.suggestion-btn {
  background: #fff; border: 1.5px solid rgba(0,0,0,0.1); border-radius: 12px;
  padding: 9px 13px; text-align: left; font-size: 13px; color: var(--ct);
  cursor: pointer; font-family: inherit; line-height: 1.4;
  transition: border-color 0.2s ease, transform 0.15s ease, background 0.2s ease;
  animation: cwBubbleIn 0.22s var(--ease-out);
}
.suggestion-btn:hover { border-color: var(--cp); background: rgba(0,217,255,0.05); transform: translateX(3px); }

/* Bot bubble markdown */
.bubble.bot h2 { font-size: 13.5px; font-weight: 700; margin: 8px 0 3px; }
.bubble.bot h3 { font-size: 13px; font-weight: 700; margin: 6px 0 2px; }
.bubble.bot h4 { font-size: 12.5px; font-weight: 600; margin: 5px 0 2px; color: var(--ctl); text-transform: uppercase; letter-spacing: 0.4px; }
.bubble.bot ul { list-style: none; padding: 0; margin: 4px 0; }
.bubble.bot ul li::before { content: '→ '; color: var(--cp); font-weight: 600; }
.bubble.bot ol { padding-left: 18px; margin: 4px 0; }
.bubble.bot li { margin: 3px 0; line-height: 1.5; }
.bubble.bot strong { font-weight: 700; }
.bubble.bot em { font-style: italic; color: var(--ctl); }
.bubble.bot code { background: #f0f1f3; padding: 1px 5px; border-radius: 4px; font-family: monospace; font-size: 12px; }
.bubble.bot hr { border: none; border-top: 1px solid rgba(0,0,0,0.08); margin: 7px 0; }
.bubble.bot .md-p { margin: 3px 0; line-height: 1.55; }
.bubble.bot a { color: var(--cp); text-decoration: underline; word-break: break-all; }

/* ══════════════════════════════════════
   INPUT
══════════════════════════════════════ */
.controls {
  padding: 11px 12px; background: var(--cbg);
  border-top: 1px solid rgba(0,0,0,0.07);
  display: flex; align-items: flex-end; gap: 9px;
}
.textarea {
  flex: 1; padding: 10px 13px;
  border: 1.5px solid rgba(0,0,0,0.1); border-radius: 12px;
  background: #f5f6f8; color: var(--ct);
  resize: none; font-family: inherit; font-size: 13.5px;
  line-height: 1.5; max-height: 110px; min-height: 42px;
  outline: none; transition: border-color 0.2s ease, background 0.2s ease;
}
.textarea:focus { border-color: var(--cp); background: #fff; }
.textarea::placeholder { color: #bbb; }
.send-btn {
  width: 42px; height: 42px; border-radius: 12px;
  background: linear-gradient(135deg, var(--cp) 0%, var(--cs) 100%);
  color: white; border: none; cursor: pointer;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  box-shadow: 0 3px 10px rgba(0,0,0,0.18);
  transition: transform 0.2s var(--ease-spring), box-shadow 0.2s ease;
}
.send-btn:hover { transform: scale(1.08); box-shadow: 0 5px 16px rgba(0,0,0,0.22); }
.send-btn:disabled { opacity: 0.4; cursor: default; transform: none; }
.send-btn svg { width: 19px; height: 19px; }

/* Staff bubble */
.bubble.staff {
  background: #fff8e1;
  border: 1px solid rgba(245,158,11,0.25);
}
.staff-label {
  display: block; font-size: 10px; font-weight: 700;
  color: #b45309; letter-spacing: 0.5px; text-transform: uppercase;
  margin-bottom: 4px;
}

/* System notice */
.system-notice {
  align-self: center;
  background: rgba(0,0,0,0.05);
  border-radius: 999px;
  padding: 5px 12px;
  font-size: 11px;
  color: var(--ctl);
  text-align: center;
  animation: cwBubbleIn 0.22s var(--ease-out);
}

/* Pre-chat form */
.prechat-form {
  width: 100%; display: flex; flex-direction: column; gap: 10px; margin-top: 4px;
}
.prechat-input {
  width: 100%; padding: 10px 13px;
  border: 1.5px solid rgba(0,0,0,0.12); border-radius: 10px;
  font-size: 13.5px; font-family: inherit; color: var(--ct);
  background: #f5f6f8; outline: none;
  transition: border-color 0.2s ease, background 0.2s ease;
}
.prechat-input:focus { border-color: var(--cp); background: #fff; }
.prechat-input::placeholder { color: #bbb; }
.prechat-error { font-size: 12px; color: #ef4444; margin: -4px 0; }
.prechat-submit {
  padding: 11px; border-radius: 10px;
  background: linear-gradient(135deg, var(--cp) 0%, var(--cs) 100%);
  color: white; border: none; font-size: 13.5px; font-weight: 600;
  font-family: inherit; cursor: pointer;
  transition: opacity 0.2s ease;
}
.prechat-submit:disabled { opacity: 0.5; cursor: default; }
.prechat-skip {
  background: none; border: none; font-size: 12px; color: var(--ctl);
  cursor: pointer; font-family: inherit; text-decoration: underline;
  padding: 2px 0; align-self: center;
}

/* AI Act Art. 50 disclosure — welcome screen inline notice */
.ai-notice {
  font-size: 11.5px; color: var(--ctl);
  background: #f0f9ff; border: 1px solid rgba(0,153,255,0.18);
  border-radius: 8px; padding: 6px 10px;
  text-align: center; margin: 4px 0;
  line-height: 1.45;
}

/* AI Act Art. 50 disclosure — persistent strip at top of chat body */
.ai-notice-strip {
  font-size: 11px; color: var(--ctl);
  background: #f0f9ff; border-bottom: 1px solid rgba(0,153,255,0.15);
  padding: 5px 12px; text-align: center; flex-shrink: 0;
}

/* Consent banner */
.consent-banner {
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
  padding: 8px 12px;
  background: #fffbeb;
  border-top: 1px solid rgba(245,158,11,0.25);
  font-size: 11.5px; color: var(--ctl);
}
.consent-accept {
  flex-shrink: 0;
  padding: 4px 12px; border-radius: 6px;
  background: linear-gradient(135deg, var(--cp) 0%, var(--cs) 100%);
  color: white; border: none; font-size: 11.5px; font-weight: 600;
  font-family: inherit; cursor: pointer;
}

/* ══════════════════════════════════════
   FOOTER
══════════════════════════════════════ */
.footer {
  padding: 7px 12px; text-align: center;
  background: var(--cbg); border-top: 1px solid rgba(0,0,0,0.05);
}
.footer a {
  font-size: 11px; color: var(--ctl); text-decoration: none;
  opacity: 0.65; transition: opacity 0.2s; font-family: inherit;
}
.footer a:hover { opacity: 1; }
`;
