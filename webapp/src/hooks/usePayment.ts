import { useCallback, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { openInvoice } from '@telegram-apps/sdk-react';
import { useCreateInvoice } from '../api/hooks';

type PaymentStatus = 'idle' | 'loading' | 'paid' | 'cancelled' | 'failed';

interface UsePaymentOptions {
  product: 'vpn' | 'mtproto' | 'whatsapp';
  devices?: number;
  duration: number;
  is_extend?: boolean;
}

export function usePayment() {
  const createInvoice = useCreateInvoice();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<PaymentStatus>('idle');

  const pay = useCallback(
    async (opts: UsePaymentOptions) => {
      setStatus('loading');

      try {
        const { invoice_url } = await createInvoice.mutateAsync({
          product: opts.product,
          devices: opts.devices,
          duration: opts.duration,
          is_extend: opts.is_extend,
        });

        // Open Telegram Stars payment sheet
        const result = await openInvoice(invoice_url, 'url');

        if (result === 'paid') {
          setStatus('paid');
          queryClient.invalidateQueries({ queryKey: ['me'] });
          queryClient.invalidateQueries({ queryKey: ['subscription'] });
        } else if (result === 'cancelled') {
          setStatus('cancelled');
        } else {
          setStatus('failed');
        }

        return result;
      } catch (err) {
        setStatus('failed');
        throw err;
      }
    },
    [createInvoice, queryClient],
  );

  return { pay, status, isLoading: status === 'loading' };
}
