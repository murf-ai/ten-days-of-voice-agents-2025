export interface AppConfig {
  pageTitle: string;
  pageDescription: string;
  companyName: string;

  supportsChatInput: boolean;
  supportsVideoInput: boolean;
  supportsScreenShare: boolean;
  isPreConnectBufferEnabled: boolean;

  logo: string;
  startButtonText: string;
  accent?: string;
  logoDark?: string;
  accentDark?: string;

  // for LiveKit Cloud Sandbox
  sandboxId?: string;
  agentName?: string;
}

export const APP_CONFIG_DEFAULTS: AppConfig = {
  companyName: 'Voice Shopping',
  pageTitle: 'Voice Shopping Assistant',
  pageDescription: 'Shop with your voice - Browse products and place orders naturally',

  supportsChatInput: true,
  supportsVideoInput: false,
  supportsScreenShare: false,
  isPreConnectBufferEnabled: true,

  logo: '',  // No logo
  accent: '#2563eb',  // Blue for shopping
  logoDark: '',
  accentDark: '#3b82f6',  // Brighter blue for dark mode
  startButtonText: 'Start Shopping',

  // for LiveKit Cloud Sandbox
  sandboxId: undefined,
  agentName: undefined,
};
