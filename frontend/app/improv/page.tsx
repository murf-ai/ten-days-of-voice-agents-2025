import { headers } from 'next/headers';
import { App } from '@/components/app/app';
import { getAppConfig } from '@/lib/utils';

export default async function Page() {
  const hdrs = await headers();
  const appConfig = await getAppConfig(hdrs);

  // Override to run the Improv Battle host
  const improvConfig = {
    ...appConfig,
    agentName: 'ImprovBattleAgent',
    startButtonText: 'Start Improv Battle',
  };

  return <App appConfig={improvConfig} />;
}
