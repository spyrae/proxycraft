import { useMemo } from 'react';
import {
  useLaunchParams,
  initDataUser,
  themeParams,
  hapticFeedback,
} from '@telegram-apps/sdk-react';

export function useTelegram() {
  const launchParams = useLaunchParams(true);

  const user = useMemo(() => {
    try {
      return initDataUser();
    } catch {
      return undefined;
    }
  }, []);

  return {
    user,
    launchParams,
    themeParams,
    hapticFeedback,
  };
}
