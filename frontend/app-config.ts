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
  companyName: 'Wellness Companion',
  pageTitle: 'Health & Wellness Voice Companion',
  pageDescription: 'Your daily check-in companion for mood, energy, and intentions',

  supportsChatInput: true,
  supportsVideoInput: false,
  supportsScreenShare: false,
  isPreConnectBufferEnabled: true,

  logo: '/lk-logo.svg',
  accent: '#10b981',
  logoDark: '/lk-logo-dark.svg',
  accentDark: '#34d399',
  startButtonText: 'Start Daily Check-in',

  // for LiveKit Cloud Sandbox
  sandboxId: undefined,
  agentName: undefined,
};
