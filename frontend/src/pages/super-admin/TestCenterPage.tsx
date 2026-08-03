import { useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { Check, Copy, ExternalLink, MessageCircle, MessageSquare, Phone, Plus, RefreshCw } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import {
  useCreateVoiceAgent,
  useOrgChannelStatus,
  useOrganization,
  useProvisionVoiceAgent,
} from "../../api/organizations";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Spinner } from "../../components/ui/Spinner";

// Real production embed URL — the actual client-facing embed snippet shown
// to admins to copy onto a client's site.
const CW_SCRIPT_URL = "https://genaitech.be/widget/cw.js";
// Local preview only: served from public/cw.js, a manual copy of
// widget/dist/cw.js. Re-copy after rebuilding the widget
// (cd widget && npm run build && cp dist/cw.js ../frontend/public/cw.js) or
// this preview silently serves stale code.
const LOCAL_CW_SCRIPT_PATH = "/cw.js";

function ConfiguredBadge({ configured }: { configured: boolean }) {
  return configured ? <Badge variant="success">Configured</Badge> : <Badge variant="neutral">Not Configured</Badge>;
}

function StatusDot({ configured }: { configured: boolean }) {
  if (!configured) {
    return <span className="h-2 w-2 shrink-0 rounded-full bg-slate-300" title="Not configured" />;
  }
  return (
    <span className="relative flex h-2 w-2 shrink-0" title="Configured">
      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
      <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
    </span>
  );
}

function CardHeader({ icon, title, configured }: { icon: ReactNode; title: string; configured: boolean }) {
  return (
    <div className="mb-4 flex items-center gap-2">
      {icon}
      <h3 className="text-lg font-medium tracking-tight text-slate-800 dark:text-slate-100">{title}</h3>
      <StatusDot configured={configured} />
      <div className="ml-auto">
        <ConfiguredBadge configured={configured} />
      </div>
    </div>
  );
}

function SetupWizardPrompt({ orgId, message }: { orgId: string; message: string }) {
  return (
    <div className="rounded-lg bg-slate-50 dark:bg-slate-800/50 p-4 text-sm text-slate-600 dark:text-slate-300">
      <p>{message}</p>
      <Link
        to={`/admin/organizations/${orgId}/setup`}
        className="mt-2 inline-block text-sm font-medium text-indigo-600 hover:underline"
      >
        Go to Setup Wizard →
      </Link>
    </div>
  );
}

function WebChatTestCard({ orgId, configured }: { orgId: string; configured: boolean }) {
  const [copied, setCopied] = useState(false);

  // A real page with just the real embed script on it, in an iframe — not a
  // programmatic init() call into a shared container. This intentionally
  // shows the actual production experience (a floating launcher bubble the
  // visitor has to click), same as it behaves on a client's real site,
  // rather than a modified "always open, inline" version that would look
  // and behave differently from what customers actually see.
  const previewSrcDoc = `<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <style>
      * { box-sizing: border-box; }
      body { margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f1f5f9; min-height: 100vh; }
      .page-hint { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); text-align: center; color: #94a3b8; user-select: none; pointer-events: none; }
      .page-hint svg { margin: 0 auto 8px; opacity: 0.4; }
      .page-hint p { font-size: 13px; margin: 0; }
    </style>
  </head>
  <body>
    <div class="page-hint">
      <svg width="32" height="32" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>
      <p>Click the chat bubble →</p>
    </div>
    <script src="${window.location.origin}${LOCAL_CW_SCRIPT_PATH}" data-org-id="${orgId}" data-api-base="${import.meta.env.VITE_API_URL}"></script>
  </body>
</html>`;

  const embedCode = `<script src="${CW_SCRIPT_URL}" data-org-id="${orgId}"></script>`;

  function handleCopy() {
    void navigator.clipboard.writeText(embedCode).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <Card>
      <CardHeader icon={<MessageSquare className="h-5 w-5 text-indigo-600" />} title="Web Chat" configured={configured} />

      {/* Live preview */}
      <div className="rounded-xl overflow-hidden border border-slate-200 dark:border-slate-700 shadow-sm">
        {/* Preview chrome bar */}
        <div className="flex items-center gap-2 px-3 py-2 bg-slate-100 dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700">
          <span className="h-2.5 w-2.5 rounded-full bg-red-400" />
          <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
          <span className="ml-2 flex-1 rounded-md bg-white dark:bg-slate-700 px-3 py-1 text-[11px] text-slate-400 dark:text-slate-500 font-mono truncate">
            yourwebsite.com
          </span>
        </div>
        <iframe
          title="Web chat widget preview"
          srcDoc={previewSrcDoc}
          className="h-175 w-full bg-slate-50 dark:bg-slate-900"
          sandbox="allow-scripts allow-same-origin allow-forms"
        />
      </div>

      <p className="mt-2 text-xs text-slate-400 dark:text-slate-500">
        Click the chat bubble in the bottom-right corner — this is exactly what your client&apos;s visitors will see.
      </p>

      {/* Embed code */}
      <div className="mt-5 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden">
        <div className="flex items-center justify-between px-4 py-2.5 bg-slate-50 dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700">
          <span className="text-xs font-semibold uppercase tracking-widest text-slate-400 dark:text-slate-500">
            Embed Code
          </span>
          <Button size="sm" variant="secondary" onClick={handleCopy}>
            {copied ? (
              <>
                <Check className="h-3.5 w-3.5 text-emerald-500" />
                Copied!
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5" />
                Copy
              </>
            )}
          </Button>
        </div>
        <pre className="overflow-x-auto bg-slate-900 dark:bg-slate-950 px-4 py-3 text-xs text-slate-200 leading-relaxed">
          <code>{embedCode}</code>
        </pre>
      </div>
      <p className="mt-2 text-xs text-slate-400 dark:text-slate-500">
        Paste this snippet into the client&apos;s website HTML just before <code className="font-mono">&lt;/body&gt;</code>.
      </p>
    </Card>
  );
}

function CreateAgentButton({ orgId, label }: { orgId: string; label: string }) {
  const createAgent = useCreateVoiceAgent(orgId);
  const created = createAgent.data;
  return (
    <div className="space-y-2">
      <Button
        variant="secondary"
        className="w-full"
        isLoading={createAgent.isPending}
        onClick={() => createAgent.mutate()}
      >
        <Plus className="h-4 w-4" />
        {label}
      </Button>
      {created ? (
        <p className="text-xs text-emerald-600">
          New agent created and wired to this backend: <span className="font-mono">{created.retell_agent_id}</span>
        </p>
      ) : null}
      {createAgent.isError ? (
        <p className="text-xs text-red-600 dark:text-red-400">
          Agent creation failed — check RETELL_API_KEY / APP_PUBLIC_URL and the backend logs.
        </p>
      ) : null}
    </div>
  );
}

function VoiceTestCard({
  orgId,
  configured,
  retellAgentId,
  provisioned,
}: {
  orgId: string;
  configured: boolean;
  retellAgentId: string | null;
  provisioned: boolean | null;
}) {
  const provisionAgent = useProvisionVoiceAgent(orgId);
  const result = provisionAgent.data;

  return (
    <Card>
      <CardHeader icon={<Phone className="h-5 w-5 text-indigo-600" />} title="Voice" configured={configured} />

      {retellAgentId ? (
        <div className="space-y-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">Retell Agent ID</p>
            <p className="mt-1 break-all font-mono text-sm text-slate-900 dark:text-slate-100">{retellAgentId}</p>
          </div>

          <div className="flex items-center gap-2">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">Custom LLM URL</p>
            {provisioned === true ? (
              <Badge variant="success">Provisioned</Badge>
            ) : provisioned === false ? (
              <Badge variant="warning">Not Provisioned</Badge>
            ) : (
              <Badge variant="neutral">Unknown</Badge>
            )}
          </div>

          <Button
            className="w-full"
            onClick={() =>
              window.open(`https://dashboard.retellai.com/agents/${retellAgentId}`, "_blank", "noopener,noreferrer")
            }
          >
            <ExternalLink className="h-4 w-4" />
            Test in Retell Dashboard
          </Button>

          <Button
            variant="secondary"
            className="w-full"
            isLoading={provisionAgent.isPending}
            onClick={() => provisionAgent.mutate()}
          >
            <RefreshCw className="h-4 w-4" />
            Re-provision Agent
          </Button>

          {result?.warning ? (
            <p className="text-xs text-amber-600">{result.warning}</p>
          ) : result?.provisioned ? (
            <p className="text-xs text-emerald-600">
              Agent&apos;s Custom LLM URL and webhook were updated in Retell.
            </p>
          ) : null}
          {provisionAgent.isError ? (
            <p className="text-xs text-red-600 dark:text-red-400">Re-provisioning request failed. Check the backend logs.</p>
          ) : null}

          <div className="border-t border-slate-100 dark:border-slate-800 pt-3">
            <p className="mb-2 text-xs text-slate-500 dark:text-slate-400">
              Agent misbehaving? Create a fresh one we fully control — it replaces the saved agent ID.
            </p>
            <CreateAgentButton orgId={orgId} label="Create New Agent" />
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <SetupWizardPrompt orgId={orgId} message="No Retell agent yet — create one automatically, or set an existing Agent ID in the Setup Wizard." />
          <CreateAgentButton orgId={orgId} label="Create Retell Agent" />
        </div>
      )}
    </Card>
  );
}

function WhatsAppTestCard({
  orgId,
  configured,
  phoneNumber,
}: {
  orgId: string;
  configured: boolean;
  phoneNumber: string | null;
}) {
  const waLink = phoneNumber ? `https://wa.me/${phoneNumber.replace(/\D/g, "")}?text=Hi` : null;

  return (
    <Card>
      <CardHeader icon={<MessageCircle className="h-5 w-5 text-indigo-600" />} title="WhatsApp" configured={configured} />

      {waLink ? (
        <div className="space-y-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">WhatsApp Number</p>
            <p className="mt-1 font-mono text-sm text-slate-900 dark:text-slate-100">{phoneNumber}</p>
          </div>
          <div className="flex justify-center rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4">
            <QRCodeSVG value={waLink} size={160} />
          </div>
          <Button className="w-full" onClick={() => window.open(waLink, "_blank", "noopener,noreferrer")}>
            <ExternalLink className="h-4 w-4" />
            Open in WhatsApp
          </Button>
        </div>
      ) : (
        <SetupWizardPrompt
          orgId={orgId}
          message={
            configured
              ? "WhatsApp API key is configured but phone number is missing — add it in the Setup Wizard."
              : "Configure WhatsApp in the Setup Wizard first."
          }
        />
      )}
    </Card>
  );
}

export default function TestCenterPage() {
  const { orgId = "" } = useParams();
  const { data: org } = useOrganization(orgId);
  const { data: channelStatus, isLoading } = useOrgChannelStatus(orgId);

  if (isLoading || !channelStatus) {
    return (
      <div className="flex justify-center py-12">
        <Spinner />
      </div>
    );
  }

  const noChannelsEnabled =
    !channelStatus.webchat.enabled && !channelStatus.whatsapp.enabled && !channelStatus.voice.enabled;

  return (
    <div>
      <h2 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">{org?.name ?? "Organization"} — Test Center</h2>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
        Verify each enabled channel actually works before handing this organization off to the client.
      </p>

      {noChannelsEnabled ? (
        <div className="mt-6 rounded-lg border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500 dark:text-slate-400">
          No channels are enabled for this organization yet.{" "}
          <Link to={`/admin/organizations/${orgId}/setup`} className="font-medium text-indigo-600 hover:underline">
            Enable channels in the Setup Wizard
          </Link>
        </div>
      ) : (
        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
          {channelStatus.webchat.enabled && (
            <WebChatTestCard orgId={orgId} configured={channelStatus.webchat.configured} />
          )}
          {channelStatus.voice.enabled && (
            <VoiceTestCard
              orgId={orgId}
              configured={channelStatus.voice.configured}
              retellAgentId={channelStatus.voice.retell_agent_id}
              provisioned={channelStatus.voice.provisioned}
            />
          )}
          {channelStatus.whatsapp.enabled && (
            <WhatsAppTestCard
              orgId={orgId}
              configured={channelStatus.whatsapp.configured}
              phoneNumber={channelStatus.whatsapp.phone_number}
            />
          )}
        </div>
      )}
    </div>
  );
}
